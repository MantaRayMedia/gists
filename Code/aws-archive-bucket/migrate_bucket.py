#!/usr/bin/env python3
import boto3
import argparse
import sys
import os
from botocore.exceptions import ClientError, NoCredentialsError
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import re

class S3ToS3GlacierMigrator:
    def __init__(self, profile=None, region=None):
        self.session = boto3.Session(profile_name=profile, region_name=region)
        self.s3 = self.session.client('s3')
        self.completed_files = 0
        self.failed_files = 0
        self.lock = threading.Lock()

    def log_message(self, message, level="INFO"):
        print(f"[{level}] {message}")

    def check_resources(self):
        """Verify S3 bucket exists"""
        try:
            # Check if source S3 bucket exists
            self.s3.head_bucket(Bucket=self.source_bucket)
            self.log_message(f"Source S3 bucket '{self.source_bucket}' verified")
            
            # Check if destination S3 bucket exists, create if needed
            try:
                self.s3.head_bucket(Bucket=self.destination_bucket)
                self.log_message(f"Destination S3 bucket '{self.destination_bucket}' verified")
            except ClientError:
                self.log_message(f"Destination bucket '{self.destination_bucket}' not found, creating...")
                self.s3.create_bucket(
                    Bucket=self.destination_bucket,
                    CreateBucketConfiguration={'LocationConstraint': self.session.region_name}
                )
                self.log_message(f"Destination S3 bucket '{self.destination_bucket}' created")
                
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                self.log_message(f"S3 bucket '{self.source_bucket}' not found", "ERROR")
            elif error_code == '403':
                self.log_message(f"Access denied to S3 bucket '{self.source_bucket}'", "ERROR")
            else:
                self.log_message(f"Error accessing S3 bucket: {e}", "ERROR")
            return False

    def get_bucket_size(self, bucket_name):
        """Calculate total size of bucket for progress tracking"""
        total_size = 0
        total_files = 0
        
        paginator = self.s3.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=bucket_name):
            if 'Contents' in page:
                for obj in page['Contents']:
                    total_size += obj['Size']
                    total_files += 1
        
        return total_size, total_files

    def format_size(self, size_bytes):
        """Convert bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"

    def get_destination_path(self, s3_key):
        """Determine the destination path based on --root flag"""
        if self.use_root:
            # Direct mapping: keep original S3 key
            return s3_key
        else:
            # Create folder with bucket name (strip 's3-' prefix if present)
            bucket_folder = re.sub(r'^s3-', '', self.source_bucket)
            return f"{bucket_folder}/{s3_key}"

    def copy_file_to_glacier(self, s3_object):
        """Copy a single file from source bucket to destination bucket with Glacier storage class"""
        key = s3_object['Key']
        size = s3_object['Size']
        destination_key = self.get_destination_path(key)
        
        try:
            # Copy object to destination bucket with Glacier storage class
            copy_source = {'Bucket': self.source_bucket, 'Key': key}
            
            self.s3.copy_object(
                CopySource=copy_source,
                Bucket=self.destination_bucket,
                Key=destination_key,
                StorageClass='GLACIER',  # Using S3 Glacier storage class
                MetadataDirective='COPY'
            )
            
            with self.lock:
                self.completed_files += 1
                self.log_message(f"✓ [{self.completed_files}/{self.total_files}] {key} -> {destination_key} (GLACIER)")
            
            return True, key, destination_key
            
        except Exception as e:
            with self.lock:
                self.failed_files += 1
                self.log_message(f"✗ Failed to copy {key}: {str(e)}", "ERROR")
            return False, key, str(e)

    def migrate_to_s3_glacier(self, source_bucket, destination_bucket=None, max_workers=5, use_root=False):
        """Main migration function using S3 Glacier storage class"""
        self.source_bucket = source_bucket
        self.destination_bucket = destination_bucket or f"{source_bucket}-glacier-archive"
        self.use_root = use_root
        
        if use_root:
            self.log_message(f"Starting migration: s3://{source_bucket} -> s3://{self.destination_bucket}/ (ROOT) [GLACIER STORAGE]")
        else:
            bucket_folder = re.sub(r'^s3-', '', source_bucket)
            self.log_message(f"Starting migration: s3://{source_bucket} -> s3://{self.destination_bucket}/{bucket_folder}/ [GLACIER STORAGE]")
        
        # Verify resources
        if not self.check_resources():
            return False
        
        # Get source bucket statistics
        total_size, total_files = self.get_bucket_size(self.source_bucket)
        self.total_files = total_files
        
        if total_files == 0:
            self.log_message("Source bucket is empty, nothing to migrate")
            return True
        
        self.log_message(f"Found {total_files} files, total size: {self.format_size(total_size)}")
        
        # Show migration path info
        if self.use_root:
            self.log_message("Files will be stored at DESTINATION BUCKET ROOT level with GLACIER storage class")
        else:
            bucket_folder = re.sub(r'^s3-', '', self.source_bucket)
            self.log_message(f"Files will be stored in folder: {bucket_folder}/ with GLACIER storage class")
        
        # Explain the benefits
        self.log_message("💡 Using S3 Glacier storage class (modern) instead of standalone Glacier service")
        self.log_message("💡 Benefits: S3 APIs, full region availability, lower costs, no customer deprecation")
        
        # Confirm migration
        response = input("Proceed with migration? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            self.log_message("Migration cancelled by user")
            return False
        
        # Start migration
        self.log_message(f"Starting migration with {max_workers} parallel workers...")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Get all S3 objects
            futures = []
            paginator = self.s3.get_paginator('list_objects_v2')
            
            for page in paginator.paginate(Bucket=self.source_bucket):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        future = executor.submit(self.copy_file_to_glacier, obj)
                        futures.append(future)
            
            # Wait for all copies to complete
            for future in as_completed(futures):
                pass  # Results are handled in the copy function
        
        # Apply lifecycle policy to immediately transition to Glacier
        self.apply_glacier_lifecycle_policy()
        
        # Summary
        self.log_message("=" * 60)
        self.log_message("MIGRATION SUMMARY:")
        self.log_message(f"Source: s3://{self.source_bucket}")
        if self.use_root:
            self.log_message(f"Destination: s3://{self.destination_bucket}/ (ROOT) [GLACIER STORAGE]")
        else:
            bucket_folder = re.sub(r'^s3-', '', self.source_bucket)
            self.log_message(f"Destination: s3://{self.destination_bucket}/{bucket_folder}/ [GLACIER STORAGE]")
        self.log_message(f"Total files: {self.total_files}")
        self.log_message(f"Successfully migrated: {self.completed_files}")
        self.log_message(f"Failed: {self.failed_files}")
        
        if self.failed_files == 0:
            self.log_message("🎉 All files successfully migrated to S3 Glacier storage class!")
            self.log_message("💡 Data is now in modern S3 Glacier storage (not deprecated standalone Glacier)")
        else:
            self.log_message(f"⚠️  {self.failed_files} files failed to migrate", "WARNING")
            return False
        
        return True

    def apply_glacier_lifecycle_policy(self):
        """Apply lifecycle policy to ensure all objects use Glacier storage class"""
        try:
            self.s3.put_bucket_lifecycle_configuration(
                Bucket=self.destination_bucket,
                LifecycleConfiguration={
                    'Rules': [
                        {
                            'ID': 'ImmediateGlacierTransition',
                            'Filter': {'Prefix': ''},
                            'Status': 'Enabled',
                            'Transitions': [
                                {
                                    'Days': 0,
                                    'StorageClass': 'GLACIER'
                                }
                            ]
                        }
                    ]
                }
            )
            self.log_message("✓ Lifecycle policy applied: All objects will use GLACIER storage class")
        except Exception as e:
            self.log_message(f"⚠️  Could not apply lifecycle policy: {e}", "WARNING")

def main():
    parser = argparse.ArgumentParser(description='Migrate S3 bucket to S3 Glacier storage class (modern)')
    parser.add_argument('--profile', help='AWS profile name')
    parser.add_argument('--region', help='AWS region', default='eu-west-1')
    parser.add_argument('--bucket', required=True, help='Source S3 bucket name to migrate')
    parser.add_argument('--destination', help='Destination S3 bucket name (default: {source}-glacier-archive)')
    parser.add_argument('--workers', type=int, default=5, help='Number of parallel workers (default: 5)')
    parser.add_argument('--root', action='store_true', help='Store files at destination bucket root level (default: create source-bucket-name folder)')
    
    args = parser.parse_args()
    
    print("🚀 S3 to S3 Glacier Migration Tool (MODERN)")
    print("=" * 60)
    print(f"Source: s3://{args.bucket}")
    if args.root:
        dest_bucket = args.destination or f"{args.bucket}-glacier-archive"
        print(f"Destination: s3://{dest_bucket}/ (ROOT LEVEL) [GLACIER STORAGE]")
    else:
        dest_bucket = args.destination or f"{args.bucket}-glacier-archive"
        bucket_folder = re.sub(r'^s3-', '', args.bucket)
        print(f"Destination: s3://{dest_bucket}/{bucket_folder}/ [GLACIER STORAGE]")
    print(f"Region: {args.region}")
    print(f"Profile: {args.profile or 'default'}")
    print("=" * 60)
    print("💡 Using MODERN S3 Glacier storage class (not deprecated standalone Glacier)")
    print("💡 Benefits: S3 APIs, lower costs, full AWS region availability")
    
    try:
        migrator = S3ToS3GlacierMigrator(profile=args.profile, region=args.region)
        
        success = migrator.migrate_to_s3_glacier(
            source_bucket=args.bucket,
            destination_bucket=args.destination,
            max_workers=args.workers,
            use_root=args.root
        )
        
        if success:
            print(f"✅ Migration completed successfully!")
            dest_bucket = args.destination or f"{args.bucket}-glacier-archive"
            if args.root:
                print(f"💾 All data now in S3 Glacier: s3://{dest_bucket}/")
            else:
                bucket_folder = re.sub(r'^s3-', '', args.bucket)
                print(f"💾 All data now in S3 Glacier: s3://{dest_bucket}/{bucket_folder}/")
            print("🔒 Using modern S3 Glacier storage class (not deprecated)")
        else:
            print(f"❌ Migration completed with errors")
            sys.exit(1)
            
    except NoCredentialsError:
        print("❌ AWS credentials not found. Please configure your credentials.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n⚠️  Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

