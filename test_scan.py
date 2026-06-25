import httpx
import asyncio
import json

API_BASE = "http://localhost:8000/api/v1"

async def run_test():
    async with httpx.AsyncClient() as client:
        # 0. Register/Login a new user to get an access token
        print("[*] Registering/logging in test user...")
        try:
            reg_res = await client.post(f"{API_BASE}/auth/register", json={
                "email": "test-admin@example.com",
                "password": "super-secure-password-123",
                "full_name": "Test Administrator"
            })
            if reg_res.status_code in (200, 201):
                access_token = reg_res.json()["access_token"]
                print("[+] Registered successfully.")
            else:
                # If account already exists, log in
                login_res = await client.post(f"{API_BASE}/auth/login", json={
                    "email": "test-admin@example.com",
                    "password": "super-secure-password-123"
                })
                access_token = login_res.json()["access_token"]
                print("[+] Logged in successfully.")
        except Exception as e:
            print(f"[-] Authentication failed: {e}")
            return

        auth_headers = {"Authorization": f"Bearer {access_token}"}

        # 1. Create a Scan
        print("[*] Creating a new scan...")
        scan_res = await client.post(f"{API_BASE}/scans", headers=auth_headers, json={
            "name": "Test SQLi & XSS Scan",
            "target": "https://httpbin.org",
            "config": {"aggressiveness": "high"}
        })
        scan_id = scan_res.json()["id"]
        print(f"[+] Scan created with ID: {scan_id}")

        # 2. Submit test API Security Payloads
        # We will use httpbin.org to safely simulate sending malicious payloads
        tasks = [
            {
                "method": "GET",
                "url": "https://httpbin.org/get?id=1' OR '1'='1",
                "headers": {"User-Agent": "SecurityScanner/1.0"},
                "payload": None
            },
            {
                "method": "POST",
                "url": "https://httpbin.org/post",
                "headers": {"Content-Type": "application/json"},
                "payload": {"username": "admin", "password": "' OR 1=1--"}
            },
            {
                "method": "GET",
                "url": "https://httpbin.org/get?q=<script>alert(1)</script>",
                "headers": {},
                "payload": None
            }
        ]

        print(f"[*] Submitting {len(tasks)} malicious payloads to the queue...")
        task_res = await client.post(f"{API_BASE}/scans/{scan_id}/tasks", json=tasks)
        print(f"[+] Tasks submitted: {task_res.json()}")

        # 3. Check system metrics
        print("[*] Fetching system metrics...")
        metrics_res = await client.get(f"{API_BASE}/execution/stats")
        print(f"[+] Metrics: {json.dumps(metrics_res.json(), indent=2)}")

if __name__ == "__main__":
    asyncio.run(run_test())
