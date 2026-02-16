"""
Performance comparison tool for Lambda vs EC2 deployments.
"""
import asyncio
import time
import json
import statistics
from typing import List, Dict, Any
import aiohttp


class DeploymentTester:
    """Test and compare deployment performance."""
    
    def __init__(self, lambda_url: str, ec2_url: str):
        self.lambda_url = lambda_url.rstrip('/')
        self.ec2_url = ec2_url.rstrip('/')
        self.results = {
            "lambda": {"latencies": [], "errors": []},
            "ec2": {"latencies": [], "errors": []}
        }
    
    async def test_endpoint(
        self, 
        session: aiohttp.ClientSession, 
        url: str, 
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Test a single endpoint and measure latency."""
        start_time = time.time()
        
        try:
            async with session.post(
                f"{url}/mcp",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                data = await response.json()
                latency_ms = (time.time() - start_time) * 1000
                
                return {
                    "success": response.status == 200,
                    "latency_ms": latency_ms,
                    "status": response.status,
                    "data": data
                }
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return {
                "success": False,
                "latency_ms": latency_ms,
                "error": str(e)
            }
    
    async def run_test_suite(
        self, 
        deployment: str, 
        url: str, 
        num_requests: int = 100
    ):
        """Run a suite of tests against a deployment."""
        print(f"\nTesting {deployment.upper()} deployment...")
        print(f"URL: {url}")
        print(f"Requests: {num_requests}")
        
        test_payloads = [
            {"action": "list_tools"},
            {
                "action": "invoke_tool",
                "data": {
                    "tool_name": "search",
                    "parameters": {"query": "test query", "limit": 5}
                }
            },
            {
                "action": "invoke_tool",
                "data": {
                    "tool_name": "database",
                    "parameters": {
                        "operation": "query",
                        "table": "users"
                    }
                }
            },
            {
                "action": "invoke_tool",
                "data": {
                    "tool_name": "file_ops",
                    "parameters": {
                        "operation": "list",
                        "path": "/tmp"
                    }
                }
            }
        ]
        
        async with aiohttp.ClientSession() as session:
            for i in range(num_requests):
                payload = test_payloads[i % len(test_payloads)]
                result = await self.test_endpoint(session, url, payload)
                
                if result["success"]:
                    self.results[deployment]["latencies"].append(result["latency_ms"])
                else:
                    self.results[deployment]["errors"].append(result.get("error", "Unknown error"))
                
                if (i + 1) % 10 == 0:
                    print(f"  Completed {i + 1}/{num_requests} requests...")
                
                # Small delay between requests
                await asyncio.sleep(0.1)
    
    def calculate_statistics(self, deployment: str) -> Dict[str, Any]:
        """Calculate statistics for a deployment."""
        latencies = self.results[deployment]["latencies"]
        errors = self.results[deployment]["errors"]
        
        if not latencies:
            return {
                "error": "No successful requests",
                "total_errors": len(errors)
            }
        
        return {
            "requests_total": len(latencies) + len(errors),
            "requests_successful": len(latencies),
            "requests_failed": len(errors),
            "success_rate": len(latencies) / (len(latencies) + len(errors)) * 100,
            "latency_mean_ms": statistics.mean(latencies),
            "latency_median_ms": statistics.median(latencies),
            "latency_min_ms": min(latencies),
            "latency_max_ms": max(latencies),
            "latency_p95_ms": statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else max(latencies),
            "latency_p99_ms": statistics.quantiles(latencies, n=100)[98] if len(latencies) >= 100 else max(latencies),
            "latency_stddev_ms": statistics.stdev(latencies) if len(latencies) > 1 else 0
        }
    
    def generate_comparison_report(self) -> Dict[str, Any]:
        """Generate a comparison report."""
        lambda_stats = self.calculate_statistics("lambda")
        ec2_stats = self.calculate_statistics("ec2")
        
        report = {
            "timestamp": time.time(),
            "lambda": lambda_stats,
            "ec2": ec2_stats,
            "comparison": {}
        }
        
        # Calculate comparative metrics
        if "latency_mean_ms" in lambda_stats and "latency_mean_ms" in ec2_stats:
            report["comparison"] = {
                "latency_difference_ms": lambda_stats["latency_mean_ms"] - ec2_stats["latency_mean_ms"],
                "latency_difference_percent": (
                    (lambda_stats["latency_mean_ms"] - ec2_stats["latency_mean_ms"]) 
                    / ec2_stats["latency_mean_ms"] * 100
                ),
                "reliability_lambda": lambda_stats["success_rate"],
                "reliability_ec2": ec2_stats["success_rate"],
                "faster_deployment": "ec2" if ec2_stats["latency_mean_ms"] < lambda_stats["latency_mean_ms"] else "lambda"
            }
        
        return report
    
    def print_report(self):
        """Print a formatted comparison report."""
        report = self.generate_comparison_report()
        
        print("\n" + "="*80)
        print("DEPLOYMENT COMPARISON REPORT")
        print("="*80)
        
        for deployment in ["lambda", "ec2"]:
            print(f"\n{deployment.upper()} Deployment:")
            print("-" * 40)
            stats = report[deployment]
            
            if "error" in stats:
                print(f"  ⚠️  {stats['error']}")
                continue
            
            print(f"  Total Requests:      {stats['requests_total']}")
            print(f"  Successful:          {stats['requests_successful']}")
            print(f"  Failed:              {stats['requests_failed']}")
            print(f"  Success Rate:        {stats['success_rate']:.2f}%")
            print(f"  Mean Latency:        {stats['latency_mean_ms']:.2f} ms")
            print(f"  Median Latency:      {stats['latency_median_ms']:.2f} ms")
            print(f"  Min Latency:         {stats['latency_min_ms']:.2f} ms")
            print(f"  Max Latency:         {stats['latency_max_ms']:.2f} ms")
            print(f"  P95 Latency:         {stats['latency_p95_ms']:.2f} ms")
            print(f"  P99 Latency:         {stats['latency_p99_ms']:.2f} ms")
            print(f"  Std Deviation:       {stats['latency_stddev_ms']:.2f} ms")
        
        if report["comparison"]:
            print("\n" + "="*80)
            print("COMPARISON ANALYSIS")
            print("="*80)
            comp = report["comparison"]
            print(f"  Faster Deployment:   {comp['faster_deployment'].upper()}")
            print(f"  Latency Difference:  {abs(comp['latency_difference_ms']):.2f} ms ({abs(comp['latency_difference_percent']):.2f}%)")
            print(f"  Lambda Reliability:  {comp['reliability_lambda']:.2f}%")
            print(f"  EC2 Reliability:     {comp['reliability_ec2']:.2f}%")
        
        print("\n" + "="*80)
        
        return report


async def main():
    """Main comparison function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Compare Lambda and EC2 deployments")
    parser.add_argument("--lambda-url", required=True, help="Lambda API endpoint URL")
    parser.add_argument("--ec2-url", required=True, help="EC2 API endpoint URL")
    parser.add_argument("--requests", type=int, default=100, help="Number of requests per deployment")
    
    args = parser.parse_args()
    
    tester = DeploymentTester(args.lambda_url, args.ec2_url)
    
    # Test both deployments
    await tester.run_test_suite("lambda", args.lambda_url, args.requests)
    await tester.run_test_suite("ec2", args.ec2_url, args.requests)
    
    # Generate and print report
    report = tester.print_report()
    
    # Save report to file
    with open("comparison_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\nDetailed report saved to: comparison_report.json")


if __name__ == "__main__":
    asyncio.run(main())
