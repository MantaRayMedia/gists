#!/usr/bin/env python3
"""
waf_attach.py
=============
Creates a new WAFv2 WebACL (CLOUDFRONT scope) with all standard rule groups
from the CloudFormation template, then attaches it to the specified CloudFront
distribution — replacing any existing WAF association.

Usage:
    python waf_attach.py \\
        --cf-id  E1EXAMPLE123456 \\
        --waf-name MyAppWebACL \\
        --profile my-aws-profile

    # Dry-run (plan only, no AWS changes):
    python waf_attach.py --cf-id E1EXAMPLE123456 --waf-name MyAppWebACL \\
        --profile my-aws-profile --dry-run

Notes:
    - WAFv2 CLOUDFRONT scope is a GLOBAL service; the boto3 client is always
      created in us-east-1 regardless of your default region.
    - CloudFront updates require an ETag from the current distribution config;
      the script fetches it automatically.
"""

import argparse
import json
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


# ---------------------------------------------------------------------------
# WAF rule definitions  (mirrors the CloudFormation template exactly)
# ---------------------------------------------------------------------------
# Rule group ARNs are account-specific; ${AWS::AccountId} is resolved at
# runtime from STS so the script stays account-agnostic.

def build_rules(account_id: str) -> list:
    """Return the full ordered list of WAF rules for the standard WebACL."""

    def rg(name: str, priority: int, arn: str, metric: str) -> dict:
        """Helper: RuleGroupReferenceStatement rule."""
        return {
            "Name": name,
            "Priority": priority,
            "OverrideAction": {"None": {}},
            "Statement": {
                "RuleGroupReferenceStatement": {"ARN": arn}
            },
            "VisibilityConfig": {
                "SampledRequestsEnabled": True,
                "CloudWatchMetricsEnabled": True,
                "MetricName": metric,
            },
        }

    def mg(name: str, priority: int, vendor: str, rule_name: str, metric: str,
           rule_action_overrides: list = None,
           scope_down: dict = None) -> dict:
        """Helper: ManagedRuleGroupStatement rule."""
        stmt: dict = {
            "ManagedRuleGroupStatement": {
                "VendorName": vendor,
                "Name": rule_name,
            }
        }
        if scope_down:
            stmt["ManagedRuleGroupStatement"]["ScopeDownStatement"] = scope_down
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
                "MetricName": metric,
            },
        }

    base = f"arn:aws:wafv2:us-east-1:{account_id}:global/rulegroup"

    # Scope-down for CommonRuleSet: exclude ALB sticky + session cookies
    common_scope_down = {
        "NotStatement": {
            "Statement": {
                "AndStatement": {
                    "Statements": [
                        {
                            "ByteMatchStatement": {
                                "SearchString": "AWSALB",
                                "FieldToMatch": {
                                    "Cookies": {
                                        "MatchPattern": {"IncludedCookies": ["AWSALB"]},
                                        "MatchScope": "KEY",
                                        "OversizeHandling": "NO_MATCH",
                                    }
                                },
                                "TextTransformations": [{"Priority": 0, "Type": "NONE"}],
                                "PositionalConstraint": "EXACTLY",
                            }
                        },
                        {
                            "ByteMatchStatement": {
                                "SearchString": "AWSALBCORS",
                                "FieldToMatch": {
                                    "Cookies": {
                                        "MatchPattern": {"IncludedCookies": ["AWSALBCORS"]},
                                        "MatchScope": "KEY",
                                        "OversizeHandling": "NO_MATCH",
                                    }
                                },
                                "TextTransformations": [{"Priority": 0, "Type": "NONE"}],
                                "PositionalConstraint": "EXACTLY",
                            }
                        },
                        {
                            "ByteMatchStatement": {
                                "SearchString": "SSESS",
                                "FieldToMatch": {
                                    "Cookies": {
                                        "MatchPattern": {"All": {}},
                                        "MatchScope": "KEY",
                                        "OversizeHandling": "NO_MATCH",
                                    }
                                },
                                "TextTransformations": [{"Priority": 0, "Type": "NONE"}],
                                "PositionalConstraint": "STARTS_WITH",
                            }
                        },
                    ]
                }
            }
        }
    }

    return [
        rg("AllowRuleList",       0,  f"{base}/Allow-rule-list/2a54850e-60cd-4d47-9cf8-205ad60300bb",                  "AllowRuleList"),
        rg("BlockRuleList",       1,  f"{base}/Block-rule-list/dade2d30-fe28-4205-868f-de9c65de9ef7",                  "BlockRuleList"),
        rg("VPN-list-Block",      2,  f"{base}/VPN-block/0a497e7d-6ce8-4ec2-851d-9136db401412",                        "VPN-list-Block"),
        mg("AWS-AWSManagedRulesCommonRuleSet", 3, "AWS", "AWSManagedRulesCommonRuleSet",
           "AWSManagedRulesCommonRuleSet",
           rule_action_overrides=[{"Name": "SizeRestrictions_BODY", "ActionToUse": {"Allow": {}}}],
           scope_down=common_scope_down),
        mg("AWS-AWSManagedRulesKnownBadInputsRuleSet", 4, "AWS", "AWSManagedRulesKnownBadInputsRuleSet",
           "AWSManagedRulesKnownBadInputsRuleSet"),
        mg("AWS-AWSManagedRulesAmazonIpReputationList", 5, "AWS", "AWSManagedRulesAmazonIpReputationList",
           "AWSManagedRulesAmazonIpReputationList"),
        mg("AWS-AWSManagedRulesBotControlRuleSet", 6, "AWS", "AWSManagedRulesBotControlRuleSet",
           "AWSManagedRulesBotControlRuleSet"),
        rg("BlockBotsRule",       7,  f"{base}/Block-bots-rule/65ff9e46-ec26-4067-95dd-ad237bbf3f67",                  "BlockBotsRule"),
        rg("AllowStaticFilesRule",8,  f"{base}/Allows-static-files-rule/c52db705-9260-4443-8a28-7c806e592791",         "AllowStaticFilesRule"),
        rg("Google-throttle",     10, f"{base}/Google-throttle/a69399f5-8ea7-4373-9c1c-f2abf81e65fc",                  "GoogleRuleGroup"),
        rg("Facets-hit-rate-rule",11, f"{base}/Facets-hit-rate-rule/9d88dd3e-9acb-4110-9eea-c90ce8b98f98",             "Facets-hit-rate-rule"),
        rg("CountryRateLimit",    12, f"{base}/Block-country-by-rate/a07e6a3d-b69c-449b-90b8-9c485175fede",            "CountryRateLimit"),
    ]


# ---------------------------------------------------------------------------
# AWS helpers
# ---------------------------------------------------------------------------

def get_account_id(session: boto3.Session) -> str:
    sts = session.client("sts")
    return sts.get_caller_identity()["Account"]


def create_waf(wafv2, waf_name: str, rules: list, stack_name: str, dry_run: bool) -> str:
    """
    Create a new WAFv2 WebACL and return its ARN.
    If a WebACL with the same name already exists, return its ARN instead.
    """
    # Check if it already exists — list_web_acls uses manual NextMarker pagination
    next_marker = None
    while True:
        kwargs = {"Scope": "CLOUDFRONT", "Limit": 100}
        if next_marker:
            kwargs["NextMarker"] = next_marker
        resp = wafv2.list_web_acls(**kwargs)
        for acl in resp.get("WebACLs", []):
            if acl["Name"] == waf_name:
                log.warning("WebACL '%s' already exists — skipping creation, will reuse it.", waf_name)
                return acl["ARN"]
        next_marker = resp.get("NextMarker")
        if not next_marker:
            break

    log.info("Creating WebACL: %s", waf_name)
    if dry_run:
        log.info("[DRY-RUN] Would create WebACL '%s' with %d rules.", waf_name, len(rules))
        return f"arn:aws:wafv2:us-east-1:DRY_RUN_ACCOUNT:global/webacl/{waf_name}/dry-run-id"

    resp = wafv2.create_web_acl(
        Name=waf_name,
        Scope="CLOUDFRONT",
        DefaultAction={"Allow": {}},
        Rules=rules,
        VisibilityConfig={
            "SampledRequestsEnabled": True,
            "CloudWatchMetricsEnabled": True,
            "MetricName": "CloudFrontWebACLMetric",
        },
        Description=f"Managed by waf_attach.py - stack: {stack_name}",
        Tags=[
            {"Key": "ManagedBy",  "Value": "waf_attach.py"},
            {"Key": "StackName",  "Value": stack_name},
        ],
    )
    arn = resp["Summary"]["ARN"]
    log.info("WebACL created — ARN: %s", arn)
    return arn


def get_cf_config(cf_client, cf_id: str) -> tuple[dict, str]:
    """Return (distribution_config, etag) for the given CloudFront distribution."""
    resp = cf_client.get_distribution_config(Id=cf_id)
    return resp["DistributionConfig"], resp["ETag"]


def attach_waf_to_cf(cf_client, cf_id: str, waf_arn: str, dry_run: bool) -> None:
    """
    Attach (or replace) the WAF WebACL on a CloudFront distribution.
    Fetches the current ETag automatically; replaces any existing WAF.
    """
    config, etag = get_cf_config(cf_client, cf_id)

    existing_waf = config.get("WebAclId", "")
    if existing_waf:
        log.warning(
            "CloudFront distribution %s already has WAF attached: %s — replacing.",
            cf_id, existing_waf,
        )
    else:
        log.info("No existing WAF on distribution %s.", cf_id)

    config["WebAclId"] = waf_arn

    if dry_run:
        log.info("[DRY-RUN] Would update distribution %s with WebAclId=%s", cf_id, waf_arn)
        return

    log.info("Updating CloudFront distribution %s ...", cf_id)
    cf_client.update_distribution(
        Id=cf_id,
        IfMatch=etag,
        DistributionConfig=config,
    )
    log.info("CloudFront distribution updated. Deployment is now in progress (may take a few minutes).")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a WAFv2 WebACL and attach it to a CloudFront distribution.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python waf_attach.py --cf-id E1ABC123 --waf-name MyWAF --profile prod-account
  python waf_attach.py --cf-id E1ABC123 --waf-name MyWAF --profile prod-account --dry-run
        """,
    )
    parser.add_argument("--cf-id",    required=True, help="CloudFront distribution ID (e.g. E1ABC123456)")
    parser.add_argument("--waf-name", required=True, help="Name for the new WAFv2 WebACL")
    parser.add_argument("--profile",  required=True, help="AWS named profile (~/.aws/credentials)")
    parser.add_argument("--stack-name", default="manual", help="Optional stack name tag on the WebACL (default: manual)")
    parser.add_argument("--dry-run",  action="store_true", help="Plan only — no AWS resources will be created or modified")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.dry_run:
        log.info("=== DRY-RUN MODE — no changes will be made ===")

    # Build session
    try:
        session = boto3.Session(profile_name=args.profile)
    except Exception as exc:
        log.error("Could not create boto3 session with profile '%s': %s", args.profile, exc)
        sys.exit(1)

    # Resolve account ID (needed to build rule group ARNs)
    try:
        account_id = get_account_id(session)
        log.info("AWS account: %s", account_id)
    except (BotoCoreError, ClientError) as exc:
        log.error("Failed to resolve account ID: %s", exc)
        sys.exit(1)

    # WAFv2 must always be us-east-1 for CLOUDFRONT scope
    wafv2 = session.client("wafv2", region_name="us-east-1")
    cf    = session.client("cloudfront")

    rules = build_rules(account_id)
    log.info("Built %d WAF rules.", len(rules))

    # 1. Create (or reuse) WebACL
    try:
        waf_arn = create_waf(wafv2, args.waf_name, rules, args.stack_name, args.dry_run)
    except (BotoCoreError, ClientError) as exc:
        log.error("Failed to create WebACL: %s", exc)
        sys.exit(1)

    log.info("WebACL ARN: %s", waf_arn)

    # 2. Attach to CloudFront
    try:
        attach_waf_to_cf(cf, args.cf_id, waf_arn, args.dry_run)
    except (BotoCoreError, ClientError) as exc:
        log.error("Failed to update CloudFront distribution: %s", exc)
        sys.exit(1)

    if args.dry_run:
        log.info("=== DRY-RUN complete — no changes were made ===")
    else:
        log.info("Done. WAF '%s' is now attached to CloudFront distribution %s.", args.waf_name, args.cf_id)


if __name__ == "__main__":
    main()