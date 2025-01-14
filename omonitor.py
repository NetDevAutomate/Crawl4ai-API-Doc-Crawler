import requests
import time
from datetime import datetime
import psutil
import json
import os
from typing import Dict, List, Optional

class OllamaMonitor:
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url

    def get_models(self) -> List[Dict]:
        """Get list of installed models."""
        try:
            response = requests.get(f"{self.base_url}/api/tags")
            if response.status_code == 200:
                return response.json()['models']
            else:
                print(f"Error getting models - Status code: {response.status_code}")
                return []
        except Exception as e:
            print(f"Error getting models: {e}")
            return []

    def get_active_model(self) -> Optional[Dict]:
        """Check if there's any active model generation."""
        try:
            response = requests.get(f"{self.base_url}/api/status")
            if response.status_code == 200:
                return response.json()
            return None
        except requests.exceptions.RequestException:
            return None

    def find_ollama_processes(self) -> List[psutil.Process]:
        """Find all Ollama-related processes."""
        ollama_processes = []
        
        # Use ps command on macOS to find Ollama processes
        try:
            import subprocess
            ps_output = subprocess.check_output(['ps', '-ax', '-o', 'pid,command']).decode()
            for line in ps_output.split('\n'):
                if 'ollama' in line.lower():
                    try:
                        pid = int(line.split()[0])
                        ollama_processes.append(psutil.Process(pid))
                    except (IndexError, ValueError, psutil.NoSuchProcess):
                        continue
        except subprocess.SubprocessError:
            print("Error running ps command")
        
        return ollama_processes

    def get_process_stats(self) -> List[Dict]:
        """Get Ollama process statistics."""
        stats = []
        processes = self.find_ollama_processes()
        
        for proc in processes:
            try:
                cmdline = ' '.join(proc.cmdline()).lower()
                proc_type = 'unknown'
                
                # Determine process type
                if 'serve' in cmdline:
                    proc_type = 'server'
                elif 'runner' in cmdline:
                    proc_type = 'model-runner'
                elif 'helper' in cmdline:
                    continue  # Skip helper processes

                # Basic process info
                proc_stats = {
                    'type': proc_type,
                    'pid': proc.pid,
                    'status': proc.status(),
                    'cpu_percent': 0.0,
                    'memory_percent': 0.0,
                    'threads': 0,
                    'connections': 0,
                    'open_files': 0,
                    'rss': 0,
                    'vms': 0
                }

                # Try to get detailed stats
                try:
                    proc_stats.update({
                        'cpu_percent': proc.cpu_percent(interval=0.1),
                        'memory_percent': proc.memory_percent(),
                        'threads': proc.num_threads(),
                        'connections': len(proc.connections()),
                        'open_files': len(proc.open_files()),
                    })
                    
                    # Memory info
                    try:
                        mem_info = proc.memory_info()
                        proc_stats.update({
                            'rss': mem_info.rss / 1024 / 1024,  # Convert to MB
                            'vms': mem_info.vms / 1024 / 1024,  # Convert to MB
                        })
                    except psutil.AccessDenied:
                        pass
                        
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    pass

                stats.append(proc_stats)
                
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            except Exception as e:
                print(f"Error getting process stats: {e}")
                continue
                
        return stats

    def monitor(self, interval: int = 2):
        """Monitor Ollama activity continuously."""
        print("Starting Ollama activity monitor...")
        print(f"Base URL: {self.base_url}")
        
        while True:
            try:
                # Get current timestamp
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"\n=== Status at {current_time} ===")

                # Check active model status
                active_status = self.get_active_model()
                if active_status:
                    print("\nActive Model Status:")
                    print(json.dumps(active_status, indent=2))

                # Get installed models
                models = self.get_models()
                if models:
                    print("\nInstalled Models:")
                    for model in models:
                        size_mb = float(model['size']) / (1024 * 1024)  # Convert to MB
                        print(f"- {model['name']} (Size: {size_mb:.2f} MB)")

                # Get process statistics
                stats = self.get_process_stats()
                if stats:
                    print("\nProcess Statistics:")
                    for proc_stats in stats:
                        print(f"\n{proc_stats['type'].upper()} Process (PID: {proc_stats['pid']}):")
                        print(f"Status: {proc_stats['status']}")
                        if proc_stats['cpu_percent']:
                            print(f"CPU Usage: {proc_stats['cpu_percent']:.1f}%")
                        if proc_stats['rss']:
                            print(f"Memory (RSS): {proc_stats['rss']:.1f} MB")
                        if proc_stats['vms']:
                            print(f"Memory (VMS): {proc_stats['vms']:.1f} MB")
                        if proc_stats['memory_percent']:
                            print(f"Memory %: {proc_stats['memory_percent']:.1f}%")
                        if proc_stats['threads']:
                            print(f"Threads: {proc_stats['threads']}")
                        if proc_stats['connections']:
                            print(f"Network Connections: {proc_stats['connections']}")
                        if proc_stats['open_files']:
                            print(f"Open Files: {proc_stats['open_files']}")
                else:
                    print("\nNo Ollama processes found!")

                # Wait for next interval
                time.sleep(interval)

            except KeyboardInterrupt:
                print("\nStopping monitor...")
                break
            except Exception as e:
                print(f"\nError: {e}")
                time.sleep(interval)

if __name__ == "__main__":
    monitor = OllamaMonitor()
    monitor.monitor(interval=2)