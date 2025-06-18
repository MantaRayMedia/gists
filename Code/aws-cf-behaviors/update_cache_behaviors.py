import boto3
import json
import argparse
import sys
from botocore.exceptions import ClientError


def load_config(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Failed to load config file {path}: {e}")
        sys.exit(1)


def get_distribution_config(client, distribution_id):
    try:
        response = client.get_distribution_config(Id=distribution_id)
        return response['DistributionConfig'], response['ETag']
    except ClientError as e:
        print(f"❌ Error fetching distribution config: {e}")
        sys.exit(1)


def behavior_exists(existing_behaviors, new_behavior):
    return any(b['PathPattern'] == new_behavior['PathPattern'] for b in existing_behaviors)


def build_behavior(conf):
    behavior = {
        "PathPattern": conf["PathPattern"],
        "TargetOriginId": conf["TargetOriginId"],
        "ViewerProtocolPolicy": conf["ViewerProtocolPolicy"],
        "AllowedMethods": {
            "Quantity": 3,
            "Items": ["HEAD", "GET", "OPTIONS"],
            "CachedMethods": {
                "Quantity": 2,
                "Items": ["HEAD", "GET"]
            }
        },
        "Compress": conf.get("Compress", False),
        "SmoothStreaming": False,
        "TrustedSigners": {"Enabled": False, "Quantity": 0},
        "TrustedKeyGroups": {"Enabled": False, "Quantity": 0},
        "LambdaFunctionAssociations": {"Quantity": 0},
        "FunctionAssociations": {"Quantity": 0},
        "FieldLevelEncryptionId": "",
        "CachePolicyId": conf["CachePolicyId"],
        "OriginRequestPolicyId": conf["OriginRequestPolicyId"],
        "ResponseHeadersPolicyId": conf.get("ResponseHeadersPolicyId", "")
    }

    # Add ResponseHeadersPolicyId only if present and non-empty
    if "ResponseHeadersPolicyId" in conf and conf["ResponseHeadersPolicyId"]:
        behavior["ResponseHeadersPolicyId"] = conf["ResponseHeadersPolicyId"]

    return behavior


def add_behaviors(client, distribution_id, config):
    dist_config, etag = get_distribution_config(client, distribution_id)

    # Make sure CacheBehaviors and Items are defined properly
    if 'CacheBehaviors' not in dist_config:
        dist_config['CacheBehaviors'] = {'Quantity': 0, 'Items': []}
    elif 'Items' not in dist_config['CacheBehaviors']:
        dist_config['CacheBehaviors']['Items'] = []

    behaviors = dist_config['CacheBehaviors']
    existing_items = behaviors['Items']

    for behavior_conf in config:
        if behavior_exists(existing_items, behavior_conf):
            print(f"ℹ️ Behavior {behavior_conf['PathPattern']} already exists. Skipping.")
            continue

        print(f"➕ Adding behavior {behavior_conf['PathPattern']}")
        new_behavior = build_behavior(behavior_conf)
        existing_items.append(new_behavior)
        behaviors['Quantity'] = len(existing_items)

    try:
        client.update_distribution(
            Id=distribution_id,
            IfMatch=etag,
            DistributionConfig=dist_config
        )
        print("✅ Distribution updated successfully.")
    except ClientError as e:
        print(f"❌ Error updating distribution: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Update CloudFront distribution with additional cache behaviors.")
    parser.add_argument("--id", required=True, help="CloudFront distribution ID")
    parser.add_argument("--config", default="behaviors_config.json", help="Path to behaviors config file")
    parser.add_argument("--profile", default=None, help="AWS CLI profile to use")

    args = parser.parse_args()

    session = boto3.Session(profile_name=args.profile) if args.profile else boto3.Session()
    client = session.client("cloudfront")

    config = load_config(args.config)
    add_behaviors(client, args.id, config)


if __name__ == "__main__":
    main()
