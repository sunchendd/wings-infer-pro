#!/usr/bin/env python3
"""
CleanCode API Client for xfusion system
Handles authentication and retrieval of MR review results
"""

import requests
import json
import random
import argparse
import os
from pathlib import Path
import urllib3
from typing import Dict, List, Optional

try:
    from .ensure_references import ensure_references
except ImportError:
    from ensure_references import ensure_references

# Suppress SSL warnings when verify_ssl is False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def ensure_references_available() -> bool:
    """Ensure references are extracted before downstream rule lookup."""
    script_dir = Path(__file__).resolve().parent
    skill_root = script_dir.parent
    return ensure_references(skill_root=skill_root) == 0


class CleanCodeClient:
    """Client for interacting with xfusion CleanCode API"""

    def __init__(self, config_path: str = None, verify_ssl: bool = False):
        """
        Initialize the CleanCode client

        Args:
            config_path: Path to config.json file containing credentials
            verify_ssl: Whether to verify SSL certificates (default: False)
        """
        self.session = requests.Session()
        self.session.verify = verify_ssl
        self.x_token = None

        # Load credentials from config file
        if config_path is None:
            # Default to config.json in the skill root directory (parent of scripts/)
            script_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(os.path.dirname(script_dir), "config.json")

        self.config = self._load_config(config_path)
        self.username = self.config.get("username")
        self.password = self.config.get("password")

    def _load_config(self, config_path: str) -> Dict:
        """
        Load configuration from JSON file

        Args:
            config_path: Path to config.json file

        Returns:
            Dictionary containing configuration
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Config file not found: {config_path}")
            return {}
        except json.JSONDecodeError as e:
            print(f"Invalid JSON in config file: {e}")
            return {}

    def login(self) -> bool:
        """
        Login to the xfusion portal and obtain session cookies

        Returns:
            True if login successful, False otherwise
        """
        login_url = "https://uniportal.xfusion.com/uniportal1/rest/hwidcenter/login"
        payload = {
            "loginAccount": self.username,
            "password": self.password,
            "uid": self.username
        }

        try:
            response = self.session.post(login_url, json=payload)
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            print(f"Login failed: {e}")
            return False

    def get_x_token(self) -> Optional[str]:
        """
        Retrieve X-Token for API authentication

        Returns:
            X-Token string if successful, None otherwise
        """
        if not self.session.cookies:
            print("Not logged in. Please call login() first.")
            return None

        token_url = f"https://libing.xfusion.com/v3/v1/italm/gatewayservice/cleancode/token"
        params = {
            "username": self.username,
            "cacheid": str(random.random())
        }

        try:
            response = self.session.get(token_url, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("code") == 200:
                self.x_token = data.get("data")
                return self.x_token
            else:
                print(f"Failed to get token: {data.get('message')}")
                return None
        except requests.RequestException as e:
            print(f"Failed to get X-Token: {e}")
            return None

    def query_review_results(
        self,
        version_id: str,
        mr_id: str,
        rule_category: int,
        page: int = 1,
        size: int = 500
    ) -> Optional[Dict]:
        """
        Query review results for a specific category

        Args:
            version_id: The version ID from MR URL
            mr_id: The MR ID from MR URL
            rule_category: Category type (1=general, 3=security, 4=other)
            page: Page number (default: 1)
            size: Page size (default: 500)

        Returns:
            Dictionary containing review results or None if failed
        """
        if not self.x_token:
            print("No X-Token available. Please call get_x_token() first.")
            return None

        api_url = "https://cleancode-api.xfusion.com/mr-report-service/personalBug/queryPersonalRule"
        headers = {
            "X-Token": self.x_token,
            "Content-Type": "application/json"
        }
        payload = {
            "page": page,
            "size": size,
            "versionId": version_id,
            "ruleCategoryStr": rule_category,
            "mrId": mr_id
        }

        try:
            response = self.session.post(api_url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Failed to query review results: {e}")
            return None

    def get_all_review_results(
        self,
        version_id: str,
        mr_id: str
    ) -> Dict[str, List[Dict]]:
        """
        Retrieve all review results (general, security, other)

        Args:
            version_id: The version ID from MR URL
            mr_id: The MR ID from MR URL

        Returns:
            Dictionary with keys: 'general', 'security', 'other'
            Each key contains a list of review issues
        """
        results = {
            "general": [],
            "security": [],
            "other": []
        }

        # Query each category
        categories = {
            "general": 1,
            "security": 3,
            "other": 4
        }

        for category_name, category_id in categories.items():
            response = self.query_review_results(version_id, mr_id, category_id)
            if response and "rows" in response:
                results[category_name] = response["rows"]

        return results

    def parse_mr_url(self, mr_url: str) -> Optional[Dict[str, str]]:
        """
        Parse MR URL to extract versionId and mrId

        Args:
            mr_url: The MR URL string

        Returns:
            Dictionary with 'versionId' and 'mrId' or None if parsing fails
        """
        try:
            # Parse URL parameters
            if "versionId=" in mr_url and "mrid=" in mr_url:
                params = mr_url.split("?")[1]
                param_dict = {}
                for param in params.split("&"):
                    key, value = param.split("=")
                    param_dict[key] = value

                return {
                    "versionId": param_dict.get("versionId"),
                    "mrId": param_dict.get("mrid")
                }
        except Exception as e:
            print(f"Failed to parse MR URL: {e}")
            return None

    def get_review_results_from_url(self, mr_url: str) -> Optional[Dict[str, List[Dict]]]:
        """
        Convenience method to get all review results from an MR URL

        Args:
            mr_url: The MR URL string

        Returns:
            Dictionary with review results or None if failed
        """
        mr_info = self.parse_mr_url(mr_url)
        if not mr_info:
            return None

        return self.get_all_review_results(mr_info["versionId"], mr_info["mrId"])


def main():
    """Example usage of the CleanCode client"""
    parser = argparse.ArgumentParser(description="Get CleanCode review results from MR URL")
    parser.add_argument("mr_url", help="MR URL (e.g., https://cleancode-issue.xfusion.com/#/check?versionId=3990646&mrid=154565_384875)")
    parser.add_argument("--config", help="Path to config.json file", default=None)
    parser.add_argument("--output", help="Output JSON file path", default=None)
    parser.add_argument("--verify-ssl", help="Verify SSL certificates", action="store_true", default=False)

    args = parser.parse_args()

    if not ensure_references_available():
        print("Failed to prepare references. Please check references.zip and try again.")
        return

    # Initialize client
    client = CleanCodeClient(config_path=args.config, verify_ssl=args.verify_ssl)

    # Login
    if not client.login():
        print("Login failed!")
        return

    # Get X-Token
    token = client.get_x_token()
    if not token:
        print("Failed to get X-Token!")
        return

    print(f"Successfully obtained X-Token: {token[:20]}...")

    # Get all review results from URL
    results = client.get_review_results_from_url(args.mr_url)

    if results is None:
        print("Failed to get review results!")
        return

    # Print results
    print("\n=== Review Results ===")
    for category, issues in results.items():
        print(f"\n{category.upper()} ({len(issues)} issues):")
        for issue in issues:
            print(f"  - {issue.get('fileName')}:{issue.get('lineNo')} - {issue.get('ruleDesc')}")

    # Save to file if requested
    if args.output:
        # Filter to only essential fields to reduce context
        essential_fields = ["fileName", "lineNo", "ruleDesc", "scanSrc", "scanErrorDesc", "ext06", "ext07"]
        filtered_results = {}
        for category, issues in results.items():
            filtered_results[category] = [
                {k: issue.get(k) for k in essential_fields if k in issue}
                for issue in issues
            ]
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(filtered_results, f, ensure_ascii=False, indent=2)
        print(f"\nResults saved to: {args.output}")


if __name__ == "__main__":
    main()