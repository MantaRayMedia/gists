#!/usr/bin/env python3
"""
waf_diagnose.py
===============
Full diagnostic for a WAFv2 WebACL attached to a CloudFront distribution.

Checks:
  1. CloudFront distribution status (Deployed vs InProgress)
  2. WAF is actually associated with the distribution
  3. Each WAF rule's effective action (OverrideAction vs Action)
  4. Whether any rule is in COUNT-only mode (traffic passes through)
  5. Whether the WAF WebACL default action would allow blocked IPs through
  6. Sampling / CloudWatch metrics enabled per rule

Requirements:
    pip install boto3 tabulate

Usage:
    python waf_diagnose.py --cf-id E1EXAMPLE123456 --waf-name MyAppWebACL --profile my-aws-profile
"""

import argparse
import logging
import sys

import boto3
from botocore.exceptions import BotoCoreError, ClientError

try:
    from tabulate import tabulate
    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

SEPARATOR = "-" * 72


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def section(title: str) -> None:
    print(f"\n{SEPARATOR}")
    print(f"  {title}")
    print(SEPARATOR)


def ok(msg: str) -> None:
    print(f"  [OK]      {msg}")


def warn(msg: str) -> None:
    print(f"  [WARN]    {msg}")


def error(msg: str) -> None:
    print(f"  [ERROR]   {msg}")


def info(msg: str) -> None:
    print(f"  [INFO]    {msg}")


# ---------------------------------------------------------------------------
# 1. CloudFront distribution checks
# ---------------------------------------------------------------------------

def check_cloudfront(cf_client, cf_id: str) -> str | None:
    """
    Returns the WAF WebACL ARN attached to the distribution, or None.
    Also reports deployment status.
    """
    section("1. CloudFront Distribution Status")
    try:
        resp = cf_client.get_distribution(Id=cf_id)
    except ClientError as exc:
        error(f"Could not fetch distribution {cf_id}: {exc}")
        return None

    dist   = resp["Distribution"]
    config = dist["DistributionConfig"]
    status = dist["Status"]
    domain = dist["DomainName"]

    info(f"Distribution ID : {cf_id}")
    info(f"Domain          : {domain}")

    if status == "Deployed":
        ok(f"Status          : {status}  (fully propagated — WAF is active)")
    else:
        warn(f"Status          : {status}  (still propagating — WAF rules may not be enforced yet)")
        warn("CloudFront changes can take 5–15 minutes to fully deploy globally.")

    waf_arn = config.get("WebAclId", "")
    if waf_arn:
        ok(f"WAF attached    : {waf_arn}")
    else:
        error("No WAF WebACL is attached to this distribution!")
        warn("Run waf_attach.py to attach one.")

    return waf_arn or None


# ---------------------------------------------------------------------------
# 2. WAF WebACL lookup
# ---------------------------------------------------------------------------

def get_web_acl(wafv2, waf_name: str) -> dict | None:
    """Find a CLOUDFRONT-scoped WebACL by name and return its full details."""
    section("2. WAF WebACL Lookup")

    # list_web_acls uses manual NextMarker pagination
    next_marker = None
    while True:
        kwargs = {"Scope": "CLOUDFRONT", "Limit": 100}
        if next_marker:
            kwargs["NextMarker"] = next_marker
        resp = wafv2.list_web_acls(**kwargs)
        for acl in resp.get("WebACLs", []):
            if acl["Name"] == waf_name:
                info(f"Found WebACL : {acl['Name']}")
                info(f"ARN         : {acl['ARN']}")
                info(f"ID          : {acl['Id']}")
                # Fetch full details
                detail = wafv2.get_web_acl(
                    Name=acl["Name"],
                    Scope="CLOUDFRONT",
                    Id=acl["Id"],
                )
                return detail["WebACL"]
        next_marker = resp.get("NextMarker")
        if not next_marker:
            break

    error(f"WebACL '{waf_name}' not found in CLOUDFRONT scope (us-east-1).")
    return None


# ---------------------------------------------------------------------------
# 3. Cross-check: WAF ARN matches what CF has attached
# ---------------------------------------------------------------------------

def check_arn_match(cf_waf_arn: str | None, acl: dict) -> None:
    section("3. WAF <-> CloudFront ARN Cross-check")
    if not cf_waf_arn:
        error("Cannot cross-check — CloudFront has no WAF attached.")
        return
    if cf_waf_arn == acl["ARN"]:
        ok("ARN matches — the correct WebACL is attached to the distribution.")
    else:
        error("ARN MISMATCH!")
        error(f"  CloudFront has : {cf_waf_arn}")
        error(f"  WebACL ARN is  : {acl['ARN']}")
        warn("The wrong WAF is attached. Re-run waf_attach.py with the correct --waf-name.")


# ---------------------------------------------------------------------------
# 4. Default action check
# ---------------------------------------------------------------------------

def check_default_action(acl: dict) -> None:
    section("4. WebACL Default Action")
    default = acl.get("DefaultAction", {})
    if "Allow" in default:
        # Allow is correct — rules run first; default is fallback for unmatched traffic
        ok("DefaultAction: Allow  (expected — rules handle specific block/allow logic)")
    elif "Block" in default:
        warn("DefaultAction: Block  (all traffic not matched by a rule will be blocked)")
        warn("Verify this is intentional — it will block any IP not covered by a rule.")
    else:
        warn(f"DefaultAction: {default}  (unexpected value)")


# ---------------------------------------------------------------------------
# 5. Per-rule action analysis
# ---------------------------------------------------------------------------

def effective_action(rule: dict) -> str:
    """
    Determine the effective action for a rule.

    WAFv2 action precedence:
      - ManagedRuleGroup / RuleGroup rules use OverrideAction:
          None  → rule group's own actions are used (BLOCK, COUNT, etc.)
          Count → ALL actions in the group are overridden to COUNT (traffic passes)
      - Regular rules use Action: Allow | Block | Count | Captcha
    """
    override = rule.get("OverrideAction", {})
    action   = rule.get("Action", {})

    if "Count" in override:
        return "COUNT (override) — ⚠ TRAFFIC PASSES THROUGH"
    if "None" in override:
        return "RULE GROUP OWN ACTIONS (block/allow per rule inside group)"
    if "Block" in action:
        return "BLOCK"
    if "Allow" in action:
        return "ALLOW"
    if "Count" in action:
        return "COUNT — ⚠ TRAFFIC PASSES THROUGH"
    if "Captcha" in action:
        return "CAPTCHA"
    return f"UNKNOWN: {override or action}"


def check_rules(acl: dict) -> list[dict]:
    """Analyse every rule and return a list of issue dicts."""
    section("5. Rule-by-Rule Analysis")
    rules   = sorted(acl.get("Rules", []), key=lambda r: r["Priority"])
    issues  = []
    rows    = []

    for rule in rules:
        name      = rule["Name"]
        priority  = rule["Priority"]
        eff       = effective_action(rule)
        vis       = rule.get("VisibilityConfig", {})
        sampling  = vis.get("SampledRequestsEnabled", False)
        metrics   = vis.get("CloudWatchMetricsEnabled", False)

        is_count_override = "Count" in rule.get("OverrideAction", {})
        is_count_action   = "Count" in rule.get("Action", {})
        is_problematic    = is_count_override or is_count_action

        status_flag = "⚠ WARN" if is_problematic else "OK"

        rows.append([
            priority,
            name,
            eff,
            "Yes" if sampling else "No",
            "Yes" if metrics  else "No",
            status_flag,
        ])

        if is_problematic:
            issues.append({
                "name":     name,
                "priority": priority,
                "reason":   "Rule is in COUNT mode — matching requests are logged but NOT blocked.",
                "fix":      (
                    "Change OverrideAction to None: {} to restore the rule group's own block actions."
                    if is_count_override else
                    "Change Action to Block: {} to block matching requests."
                ),
            })

        if not sampling:
            issues.append({
                "name":     name,
                "priority": priority,
                "reason":   "SampledRequestsEnabled is False — you cannot see sample requests in the console.",
                "fix":      "Enable SampledRequestsEnabled in the rule's VisibilityConfig.",
            })

        if not metrics:
            issues.append({
                "name":     name,
                "priority": priority,
                "reason":   "CloudWatchMetricsEnabled is False — no CloudWatch metrics for this rule.",
                "fix":      "Enable CloudWatchMetricsEnabled in the rule's VisibilityConfig.",
            })

    headers = ["Priority", "Rule Name", "Effective Action", "Sampling", "Metrics", "Status"]
    if HAS_TABULATE:
        print("\n" + tabulate(rows, headers=headers, tablefmt="simple"))
    else:
        # Fallback plain formatting
        col_w = [max(len(str(r[i])) for r in ([headers] + rows)) for i in range(len(headers))]
        fmt   = "  ".join(f"{{:<{w}}}" for w in col_w)
        print()
        print(fmt.format(*headers))
        print("  ".join("-" * w for w in col_w))
        for row in rows:
            print(fmt.format(*row))

    return issues


# ---------------------------------------------------------------------------
# 6. Summary & recommendations
# ---------------------------------------------------------------------------

def print_summary(issues: list[dict]) -> None:
    section("6. Summary & Recommendations")
    if not issues:
        ok("No issues found. WAF rules look correctly configured.")
        return

    warn(f"{len(issues)} issue(s) found:\n")
    for i, issue in enumerate(issues, 1):
        print(f"  [{i}] Rule: {issue['name']}  (priority {issue['priority']})")
        print(f"      Problem : {issue['reason']}")
        print(f"      Fix     : {issue['fix']}")
        print()

    print("  To apply fixes, update the WebACL via:")
    print("    - AWS Console → WAF & Shield → Web ACLs → <your ACL> → Rules")
    print("    - AWS CLI: aws wafv2 update-web-acl ...")
    print("    - Re-run waf_attach.py with corrected rule definitions")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Diagnose a WAFv2 WebACL attached to a CloudFront distribution.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python waf_diagnose.py --cf-id E1ABC123 --waf-name MyWAF --profile prod-account
        """,
    )
    parser.add_argument("--cf-id",    required=True, help="CloudFront distribution ID")
    parser.add_argument("--waf-name", required=True, help="WAFv2 WebACL name")
    parser.add_argument("--profile",  required=True, help="AWS named profile (~/.aws/credentials)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        session = boto3.Session(profile_name=args.profile)
    except Exception as exc:
        log.error("Could not create boto3 session with profile '%s': %s", args.profile, exc)
        sys.exit(1)

    # WAFv2 CloudFront scope is always us-east-1
    wafv2 = session.client("wafv2", region_name="us-east-1")
    cf    = session.client("cloudfront")

    print(f"\n{'=' * 72}")
    print(f"  WAF Diagnostic Report")
    print(f"  CloudFront : {args.cf_id}")
    print(f"  WAF Name   : {args.waf_name}")
    print(f"{'=' * 72}")

    # Run all checks
    cf_waf_arn = check_cloudfront(cf, args.cf_id)
    acl        = get_web_acl(wafv2, args.waf_name)

    if not acl:
        sys.exit(1)

    check_arn_match(cf_waf_arn, acl)
    check_default_action(acl)
    issues = check_rules(acl)
    print_summary(issues)

    print(f"\n{'=' * 72}\n")
    sys.exit(1 if issues else 0)


if __name__ == "__main__":
    main()