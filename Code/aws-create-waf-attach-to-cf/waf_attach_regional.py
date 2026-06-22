#!/usr/bin/env python3
"""
waf_attach_regional.py
======================
Creates a regional WAFv2 WebACL in eu-west-1 and attaches it to an ALB.

Rules (in priority order):
  0  - Allowlist        (regional IP set, X-Forwarded-For, ALLOW)
  1  - Blacklist        (regional IP set IPv4, X-Forwarded-For, BLOCK)
  2  - Blacklist6       (regional IP set IPv6, X-Forwarded-For, BLOCK)
  3  - AWS CommonRuleSet
  4  - AWS KnownBadInputsRuleSet
  5  - AWS IPReputationList
  6  - AWS BotControlRuleSet

Usage:
    python waf_attach_regional.py \\
        --alb-arn arn:aws:elasticloadbalancing:eu-west-1:691639156536:loadbalancer/app/single-app-prod-lb/xxxxxx \\
        --waf-name MyAppWebACL-Regional \\
        --allowlist-arn arn:aws:wafv2:eu-west-1:691639156536:regional/ipset/Allowlist/xxxx \\
        --blacklist-arn arn:aws:wafv2:eu-west-1:691639156536:regional/ipset/Blacklist/xxxx \\
        --blacklist6-arn arn:aws:wafv2:eu-west-1:691639156536:regional/ipset/Blacklist6/xxxx \\
        --profile my-aws-profile

    # Dry-run
    python waf_attach_regional.py ... --dry-run
"""

import argparse
import logging
import sys

import boto3
from botocore.exceptions import BotoCoreError, ClientError

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

REGION = "eu-west-1"


# ---------------------------------------------------------------------------
# Rule definitions
# ---------------------------------------------------------------------------

def ip_rule(name: str, priority: int, ipset_arn: str, action: dict) -> dict:
    """
    IP set rule that inspects X-Forwarded-For (Position=ANY).

    Although this is a regional WAF on the ALB, all traffic arrives via
    CloudFront — so the ALB source IP is always a CloudFront edge node, not
    the real client. The real client IP is in X-Forwarded-For, appended by
    CloudFront before the request reaches the ALB.

    Position=ANY ensures we match the real client IP regardless of where it
    appears in the XFF chain (CloudFront appends its own IP at the end).

    FallbackBehavior=NO_MATCH: if XFF header is absent entirely (e.g. direct
    health checks from AWS) the rule is skipped — this is intentional so
    internal AWS traffic is not accidentally blocked.
    """
    return {
        "Name": name,
        "Priority": priority,
        "Statement": {
            "IPSetReferenceStatement": {
                "ARN": ipset_arn,
                "IPSetForwardedIPConfig": {
                    "HeaderName": "X-Forwarded-For",
                    "FallbackBehavior": "NO_MATCH",
                    "Position": "ANY",
                },
            }
        },
        "Action": action,
        "VisibilityConfig": {
            "SampledRequestsEnabled": True,
            "CloudWatchMetricsEnabled": True,
            "MetricName": name,
        },
    }


def managed_rule(name: str, priority: int, vendor: str, rule_name: str,
                 rule_action_overrides: list = None) -> dict:
    """AWS managed rule group."""
    stmt = {
        "ManagedRuleGroupStatement": {
            "VendorName": vendor,
            "Name": rule_name,
        }
    }
    if rule_action_overrides:
        stmt["ManagedRuleGroupStatement"]["RuleActionOverrides"] = rule_action_overrides

    return {
        "Name": name,
        "Priority": priority,
        "OverrideAction": {"None": {}},
        "Statement": stmt,
        "VisibilityConfig": {
            "SampledRequestsEnabled": True,
            "CloudWatchMetricsEnabled": True,
            "MetricName": name,
        },
    }


def build_rules(allowlist_arn: str, blacklist_arn: str, blacklist6_arn: str) -> list:
    return [
        # IP set rules — evaluated first
        ip_rule("Allowlist",  0, allowlist_arn,  {"Allow": {}}),
        ip_rule("Blacklist",  1, blacklist_arn,  {"Block": {}}),
        ip_rule("Blacklist6", 2, blacklist6_arn, {"Block": {}}),

        # AWS managed rules
        managed_rule(
            "AWS-AWSManagedRulesCommonRuleSet", 3, "AWS", "AWSManagedRulesCommonRuleSet",
            rule_action_overrides=[
                {"Name": "SizeRestrictions_BODY", "ActionToUse": {"Allow": {}}}
            ],
        ),
        managed_rule("AWS-AWSManagedRulesKnownBadInputsRuleSet", 4, "AWS", "AWSManagedRulesKnownBadInputsRuleSet"),
        managed_rule("AWS-AWSManagedRulesAmazonIpReputationList", 5, "AWS", "AWSManagedRulesAmazonIpReputationList"),
        managed_rule("AWS-AWSManagedRulesBotControlRuleSet",      6, "AWS", "AWSManagedRulesBotControlRuleSet"),
    ]


# ---------------------------------------------------------------------------
# WAF helpers
# ---------------------------------------------------------------------------

def get_web_acl_details(wafv2, waf_name: str) -> dict | None:
    """Return full WebACL details (including Id and LockToken) by name, or None."""
    next_marker = None
    while True:
        kwargs = {"Scope": "REGIONAL", "Limit": 100}
        if next_marker:
            kwargs["NextMarker"] = next_marker
        resp = wafv2.list_web_acls(**kwargs)
        for acl in resp.get("WebACLs", []):
            if acl["Name"] == waf_name:
                detail = wafv2.get_web_acl(
                    Name=acl["Name"],
                    Scope="REGIONAL",
                    Id=acl["Id"],
                )
                return {
                    "ARN":       acl["ARN"],
                    "Id":        acl["Id"],
                    "LockToken": detail["LockToken"],
                }
        next_marker = resp.get("NextMarker")
        if not next_marker:
            break
    return None


def create_waf(wafv2, waf_name: str, rules: list, dry_run: bool, update: bool = False) -> str:
    existing = get_web_acl_details(wafv2, waf_name)

    if existing and not update:
        log.warning("WebACL '%s' already exists — reusing. Use --update to apply rule changes.", waf_name)
        return existing["ARN"]

    if existing and update:
        log.info("Updating existing WebACL '%s' with latest rules ...", waf_name)
        if dry_run:
            log.info("[DRY-RUN] Would update WebACL '%s' with %d rules.", waf_name, len(rules))
            return existing["ARN"]
        wafv2.update_web_acl(
            Name=waf_name,
            Scope="REGIONAL",
            Id=existing["Id"],
            LockToken=existing["LockToken"],
            DefaultAction={"Allow": {}},
            Rules=rules,
            VisibilityConfig={
                "SampledRequestsEnabled": True,
                "CloudWatchMetricsEnabled": True,
                "MetricName": f"{waf_name}-Metric",
            },
        )
        log.info("WebACL updated — ARN: %s", existing["ARN"])
        return existing["ARN"]

    log.info("Creating regional WebACL: %s", waf_name)
    if dry_run:
        log.info("[DRY-RUN] Would create WebACL '%s' with %d rules.", waf_name, len(rules))
        return f"arn:aws:wafv2:{REGION}:DRY_RUN:regional/webacl/{waf_name}/dry-run-id"

    resp = wafv2.create_web_acl(
        Name=waf_name,
        Scope="REGIONAL",
        DefaultAction={"Allow": {}},
        Rules=rules,
        VisibilityConfig={
            "SampledRequestsEnabled": True,
            "CloudWatchMetricsEnabled": True,
            "MetricName": f"{waf_name}-Metric",
        },
        Description="Regional WAF managed by waf_attach_regional.py",
    )
    arn = resp["Summary"]["ARN"]
    log.info("WebACL created — ARN: %s", arn)
    return arn


# ---------------------------------------------------------------------------
# ALB helpers
# ---------------------------------------------------------------------------

def get_current_waf(wafv2, alb_arn: str) -> str | None:
    """Return the WAF ARN currently associated with this ALB, or None."""
    try:
        resp = wafv2.get_web_acl_for_resource(ResourceArn=alb_arn)
        return resp.get("WebACL", {}).get("ARN")
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        # Both codes mean no WAF is attached yet — safe to continue
        if code in ("WAFNonexistentItemException", "WAFUnavailableEntityException"):
            return None
        raise


def attach_waf_to_alb(wafv2, alb_arn: str, waf_arn: str, dry_run: bool) -> None:
    existing = get_current_waf(wafv2, alb_arn)
    if existing:
        if existing == waf_arn:
            log.info("Correct WAF already attached to ALB — nothing to do.")
            return
        log.warning("ALB already has WAF attached: %s — replacing.", existing)
        if not dry_run:
            wafv2.disassociate_web_acl(ResourceArn=alb_arn)
            log.info("Detached existing WAF.")
    else:
        log.info("No existing WAF on ALB.")

    if dry_run:
        log.info("[DRY-RUN] Would attach WAF %s to ALB %s", waf_arn, alb_arn)
        return

    wafv2.associate_web_acl(ResourceArn=alb_arn, WebACLArn=waf_arn)
    log.info("WAF attached to ALB successfully.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a regional WAFv2 WebACL and attach it to an ALB.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Tip: run this first to find your regional IP set ARNs:
  aws wafv2 list-ip-sets --scope REGIONAL --region eu-west-1 --profile <PROFILE>
        """,
    )
    parser.add_argument("--alb-arn",       required=True, help="Full ARN of the ALB")
    parser.add_argument("--waf-name",      required=True, help="Name for the new regional WebACL")
    parser.add_argument("--allowlist-arn", required=True, help="ARN of the regional Allowlist IP set")
    parser.add_argument("--blacklist-arn", required=True, help="ARN of the regional Blacklist IPv4 IP set")
    parser.add_argument("--blacklist6-arn",required=True, help="ARN of the regional Blacklist6 IPv6 IP set")
    parser.add_argument("--profile",       required=True, help="AWS named profile (~/.aws/credentials)")
    parser.add_argument("--update",   action="store_true", help="Update rules on existing WebACL instead of reusing it as-is")
    parser.add_argument("--dry-run",  action="store_true", help="Plan only — no AWS changes")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.dry_run:
        log.info("=== DRY-RUN MODE — no changes will be made ===")

    try:
        session = boto3.Session(profile_name=args.profile)
    except Exception as exc:
        log.error("Could not create session with profile '%s': %s", args.profile, exc)
        sys.exit(1)

    # Regional WAF client — eu-west-1
    wafv2 = session.client("wafv2", region_name=REGION)

    rules = build_rules(args.allowlist_arn, args.blacklist_arn, args.blacklist6_arn)
    log.info("Built %d WAF rules.", len(rules))

    try:
        waf_arn = create_waf(wafv2, args.waf_name, rules, args.dry_run, update=args.update)
    except (BotoCoreError, ClientError) as exc:
        log.error("Failed to create WebACL: %s", exc)
        sys.exit(1)

    log.info("WebACL ARN: %s", waf_arn)

    try:
        attach_waf_to_alb(wafv2, args.alb_arn, waf_arn, args.dry_run)
    except (BotoCoreError, ClientError) as exc:
        log.error("Failed to attach WAF to ALB: %s", exc)
        sys.exit(1)

    if args.dry_run:
        log.info("=== DRY-RUN complete — no changes were made ===")
    else:
        log.info("Done. Regional WAF '%s' is now protecting the ALB.", args.waf_name)


if __name__ == "__main__":
    main()
