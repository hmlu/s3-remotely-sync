#!/usr/bin/env python3

"""
Command-line interface for S3 Sync Tool
"""

import sys
import logging
import argparse
import os
from s3sync import S3Sync
from tqdm import tqdm
import time
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

console = Console()

class SyncStats:
    def __init__(self, local_path, extensions=None, blacklist=False):
        self.uploaded = 0
        self.downloaded = 0
        self.skipped = 0
        self.failed = 0
        self.start_time = time.time()
        self.total_scanned = 0
        self.to_upload = 0
        self.to_download = 0
        
    def update_scan_stats(self, total_files, to_upload, to_download):
        """update scan stats"""
        self.total_scanned = total_files
        self.to_upload = to_upload
        self.to_download = to_download
        
        table = Table(box=box.ROUNDED, show_header=False, border_style="bright_blue")
        table.add_column("Item", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("scan file count", f"{self.total_scanned:,} files")
        table.add_row("to upload", f"[yellow]↑ {self.to_upload:,} files[/yellow]")
        table.add_row("to download", f"[yellow]↓ {self.to_download:,} files[/yellow]")
        table.add_row("sync file count", f"[cyan]{self.to_upload + self.to_download:,} files[/cyan]")
        
        panel = Panel(
            table,
            title="[bold cyan]scan result[/bold cyan]",
            border_style="bright_blue",
            padding=(1, 2)
        )
        
        console.print(panel)
        
        # 创建同步进度条
        self.pbar = tqdm(
            total=self.to_upload + self.to_download,
            desc="syncing...",
            unit="files",
            bar_format="{desc:<30} |{bar:50}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}] {percentage:3.0f}%",
            colour="green",
            ncols=120,
            position=0,
            leave=True
        )

    def update_progress(self, operation, filepath):
        """update progress bar and stats"""
        filename = os.path.basename(filepath)
        if operation == 'upload':
            self.uploaded += 1
            self.pbar.set_description(f"↑ uploading: {filename[:30]:<30}")
        elif operation == 'download':
            self.downloaded += 1
            self.pbar.set_description(f"↓ downloading: {filename[:30]:<30}")
        elif operation == 'skip':
            self.skipped += 1
            self.pbar.set_description(f"○ skipped: {filename[:30]:<30}")
        elif operation == 'fail':
            self.failed += 1
            self.pbar.set_description(f"× failed: {filename[:30]:<30}")
        
        self.pbar.update(1)

    def print_summary(self):
        """print summary"""
        self.pbar.close()
        elapsed_time = time.time() - self.start_time

        table = Table(box=box.ROUNDED, show_header=False, border_style="bright_blue")
        table.add_column("Item", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("file count", f"{self.uploaded + self.downloaded:,} files")
        table.add_row("upload file", f"[green]✓ {self.uploaded:,} files[/green]")
        table.add_row("download file", f"[green]✓ {self.downloaded:,} files[/green]")
        table.add_row("skip file", f"[yellow]- {self.skipped:,} files[/yellow]")
        table.add_row("failed file", f"[red]× {self.failed:,} files[/red]")
        table.add_row("total time", f"{elapsed_time:.1f} seconds")
        
        panel = Panel(
            table,
            title="[bold cyan]sync complete statistics[/bold cyan]",
            border_style="bright_blue",
            padding=(1, 2)
        )
        
        console.print("\n")
        console.print(panel)

def main():
    """main"""
    parser = argparse.ArgumentParser(description='S3 Sync Tool')
    parser.add_argument('local_path', help='Local directory path')
    parser.add_argument('bucket', help='S3 bucket name')
    parser.add_argument('prefix', help='S3 prefix (directory)')
    parser.add_argument('--endpoint-url', help='S3-compatible service endpoint URL')
    parser.add_argument('--access-key', help='Access key ID')
    parser.add_argument('--secret-key', help='Secret access key')
    parser.add_argument('--region', help='Region name (e.g., oss-cn-beijing)')
    parser.add_argument('--extensions', nargs='+', help='File extensions to include/exclude')
    parser.add_argument('--blacklist', action='store_true', 
                       help='Treat extensions as blacklist instead of whitelist')

    args = parser.parse_args()

    # Get credentials from environment variables if not provided in arguments
    access_key = args.access_key or os.environ.get('OSS_ACCESS_KEY_ID') or os.environ.get('AWS_ACCESS_KEY_ID')
    secret_key = args.secret_key or os.environ.get('OSS_SECRET_ACCESS_KEY') or os.environ.get('AWS_SECRET_ACCESS_KEY')
    region = args.region or os.environ.get('OSS_REGION') or os.environ.get('AWS_DEFAULT_REGION')

    if not access_key or not secret_key:
        logger.error("Access key and secret key must be provided either through arguments or environment variables")
        sys.exit(1)

    try:
        stats = SyncStats(
            local_path=args.local_path,
            extensions=args.extensions,
            blacklist=args.blacklist
        )
        
        syncer = S3Sync(
            local_path=args.local_path,
            bucket=args.bucket,
            prefix=args.prefix,
            endpoint_url=args.endpoint_url,
            access_key=access_key,
            secret_key=secret_key,
            region=region,
            extensions=args.extensions,
            blacklist=args.blacklist,
            progress_callback=lambda op, fp: stats.update_progress(op, fp)
        )

        # get sync file stats
        total_files, to_upload, to_download = syncer.get_sync_stats()
        stats.update_scan_stats(total_files, to_upload, to_download)
        
        # console.print("\n[bold cyan]start sync...[/bold cyan]\n")
        
        syncer.sync()
        stats.print_summary()
    except Exception as e:
        if hasattr(stats, 'pbar'):
            stats.pbar.close()
        console.print(f"[bold red]sync failed: {str(e)}[/bold red]")
        sys.exit(1)

if __name__ == '__main__':
    main() 