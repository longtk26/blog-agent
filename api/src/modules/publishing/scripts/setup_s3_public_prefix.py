"""Make ONLY the S3_PREFIX folder of S3_BUCKET publicly readable, so published diagrams get permanent URLs (Epic 12).

    uv run python src/modules/publishing/scripts/setup_s3_public_prefix.py            # dry run: show current + planned
    uv run python src/modules/publishing/scripts/setup_s3_public_prefix.py --apply    # apply

What --apply changes:
1. Block Public Access: BlockPublicPolicy and RestrictPublicBuckets -> false (needed for a public bucket policy).
   BlockPublicAcls and IgnorePublicAcls stay true: object ACLs can never make anything public.
2. Bucket policy: one statement allowing anonymous s3:GetObject on arn:aws:s3:::<bucket>/<prefix>*.
   Any existing statements with other Sids are kept. Listing the bucket stays private.
3. Smoke test: uploads a tiny PNG under the prefix and fetches it without credentials.
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from src.configs import config  # noqa: E402

SID = "PublicReadBlogAgentDiagrams"
# 1x1 transparent PNG
PIXEL = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="apply the changes (default: dry run)")
    args = parser.parse_args()

    if not (config.s3_bucket and config.aws_access_key and config.aws_secret_key):
        print("Set S3_BUCKET, AWS_ACCESS_KEY and AWS_SECRET_KEY in blog-agent/.env first.")
        return 2

    import boto3
    from botocore.exceptions import ClientError

    s3 = boto3.client(
        "s3",
        region_name=config.s3_region,
        aws_access_key_id=config.aws_access_key.get_secret_value(),
        aws_secret_access_key=config.aws_secret_key.get_secret_value(),
    )
    bucket = config.s3_bucket
    prefix = config.s3_prefix.strip("/") + "/"

    try:
        pab = s3.get_public_access_block(Bucket=bucket)["PublicAccessBlockConfiguration"]
    except ClientError as exc:
        pab = {} if exc.response["Error"]["Code"] == "NoSuchPublicAccessBlockConfiguration" else None
        if pab is None:
            raise
    try:
        policy = json.loads(s3.get_bucket_policy(Bucket=bucket)["Policy"])
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "NoSuchBucketPolicy":
            raise
        policy = {"Version": "2012-10-17", "Statement": []}

    # Only the two flags a public bucket policy needs are changed; ACL flags are left as they are.
    new_pab = {**pab, "BlockPublicPolicy": False, "RestrictPublicBuckets": False}
    resource = f"arn:aws:s3:::{bucket}/{prefix}*"
    statement = {"Sid": SID, "Effect": "Allow", "Principal": "*", "Action": "s3:GetObject", "Resource": resource}

    def grants_public_read(s: dict) -> bool:
        actions = s.get("Action") if isinstance(s.get("Action"), list) else [s.get("Action")]
        resources = s.get("Resource") if isinstance(s.get("Resource"), list) else [s.get("Resource")]
        return (s.get("Effect") == "Allow" and s.get("Principal") in ("*", {"AWS": "*"})
                and "s3:GetObject" in actions and resource in resources and not s.get("Condition"))

    existing = [s for s in policy.get("Statement", []) if grants_public_read(s)]
    new_policy = policy if existing else {**policy, "Statement": [*policy.get("Statement", []), statement]}
    pab_change = new_pab != pab
    policy_change = not existing

    print(f"Bucket {bucket} ({config.s3_region}), public prefix '{prefix}'")
    print("Block Public Access now:", json.dumps(pab))
    print("Block Public Access:    ", f"set to {json.dumps(new_pab)}" if pab_change else "no change needed")
    if existing:
        print(f"Bucket policy: already grants public read on {resource} (Sid {existing[0].get('Sid')!r}); no change")
    else:
        print("Bucket policy planned:\n" + json.dumps(new_policy, indent=2))
    if not args.apply:
        print("\nDry run." + (" Re-run with --apply to make these changes." if pab_change or policy_change else ""))
        return 0

    if pab_change:
        s3.put_public_access_block(Bucket=bucket, PublicAccessBlockConfiguration=new_pab)
    if policy_change:
        s3.put_bucket_policy(Bucket=bucket, Policy=json.dumps(new_policy))
    print("Applied." if pab_change or policy_change else "Nothing to change.")

    key = f"{prefix}_healthcheck.png"
    s3.put_object(Bucket=bucket, Key=key, Body=PIXEL, ContentType="image/png", CacheControl="no-cache")
    url = f"https://{bucket}.s3.{config.s3_region}.amazonaws.com/{key}"
    with urllib.request.urlopen(url, timeout=15) as resp:
        ok = resp.status == 200 and resp.read() == PIXEL
    print(f"Anonymous GET {url}: {'OK' if ok else 'FAILED'}")
    private_url = f"https://{bucket}.s3.{config.s3_region}.amazonaws.com/"
    try:
        urllib.request.urlopen(private_url, timeout=15)
        print(f"WARNING: bucket listing {private_url} is public")
    except urllib.error.HTTPError as exc:
        print(f"Bucket listing stays private (HTTP {exc.code})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
