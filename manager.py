
import subprocess
import json

from dotenv import load_dotenv
from analyzer import create_analyzer_agent
# from revisor import create_revisor_agent  # assuming similar structure

def run_swe_agent(analyzer_output: dict) -> dict:
    """
    Run the SWE-Agent CLI tool and return the parsed dictionary output.
    """
    print("🚀 Running SWE-Agent...")
    
    # Construct command using analyzer output
    cmd = [
        "python", "SWE-Agent/sweagent/run/run.py", "run",
        "--config", "config.yaml",
        "--github-issue", analyzer_output["problem_statement"],  # or actual GitHub issue link
        "--file-path", analyzer_output["filepath"],
        "--paradigm", analyzer_output["paradigm"]
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        output = result.stdout.strip()
        
        # Try to extract dictionary from output (e.g., JSON block)
        json_start = output.find('{')
        json_end = output.rfind('}') + 1
        json_str = output[json_start:json_end]
        return json.loads(json_str)

    except subprocess.CalledProcessError as e:
        print("❌ SWE-Agent error:", e.stderr)
        return {"error": "SWE-Agent failed"}
    except json.JSONDecodeError:
        print("❌ Failed to parse SWE-Agent output")
        return {"error": "Invalid SWE-Agent output"}

def main(issue_link: str):
    # Step 1: Analyzer
    analyzer_output = create_analyzer_agent(issue_link)
    print("🧠 Analyzer Output:", analyzer_output)

    # Step 2: SWE-Agent
    # swe_output = run_swe_agent(analyzer_output)
    # print("🛠️ SWE-Agent Output:", swe_output)

    # # Step 3: Revisor
    # revisor_output = create_revisor_agent(swe_output)
    # print("🔍 Revisor Output:", revisor_output)


if __name__ == "__main__":
    load_dotenv()
    test_issue = "https://github.com/SWE-agent/test-repo/issues/22"
    main(test_issue)





# """
# Multi-Agent Orchestrator for Sequential Agent Execution
# Manages communication between Analyzer -> SWE-Agent -> Revisor
# Uses native Python dictionaries for efficient communication
# """

# import subprocess
# import json
# import os
# import sys
# import tempfile
# import shutil
# import importlib.util
# from pathlib import Path
# from typing import Dict, Any, Optional
# import logging

# # Set up logging
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# logger = logging.getLogger(__name__)

# class MultiAgentOrchestrator:
#     def __init__(self, 
#                  analyzer_module: str = "analyzer.py",
#                  revisor_module: str = "revisor.py", 
#                  swe_agent_dir: str = "SWE-Agent",
#                  swe_config: str = "some.yaml",
#                  temp_dir: str = None):
#         """
#         Initialize the orchestrator with paths to components
        
#         Args:
#             analyzer_module: Path to analyzer.py module
#             revisor_module: Path to revisor.py module
#             swe_agent_dir: Path to SWE-Agent directory
#             swe_config: SWE-Agent config file
#             temp_dir: Temporary directory for intermediate files
#         """
#         self.analyzer_path = analyzer_module
#         self.revisor_path = revisor_module
#         self.swe_agent_dir = Path(swe_agent_dir)
#         self.swe_config = swe_config
#         self.temp_dir = temp_dir or tempfile.mkdtemp(prefix="multi_agent_")
        
#         # Load analyzer and revisor modules
#         self.analyzer = self._load_module("analyzer", analyzer_module)
#         self.revisor = self._load_module("revisor", revisor_module)
        
#         # Ensure temp directory exists
#         os.makedirs(self.temp_dir, exist_ok=True)
        
#     def _load_module(self, module_name: str, module_path: str):
#         """
#         Dynamically load a Python module from file path
        
#         Args:
#             module_name: Name to give the module
#             module_path: Path to the .py file
            
#         Returns:
#             Loaded module object
#         """
#         try:
#             spec = importlib.util.spec_from_file_location(module_name, module_path)
#             module = importlib.util.module_from_spec(spec)
#             spec.loader.exec_module(module)
#             logger.info(f"Successfully loaded {module_name} from {module_path}")
#             return module
#         except Exception as e:
#             logger.error(f"Failed to load {module_name} from {module_path}: {str(e)}")
#             raise
        
#     def run_analyzer(self, github_issue_url: str) -> Dict[str, Any]:
#         """
#         Run the analyzer agent with GitHub issue URL
        
#         Args:
#             github_issue_url: URL to GitHub issue
            
#         Returns:
#             Dictionary with analyzer results
#         """
#         logger.info(f"Running analyzer for issue: {github_issue_url}")
        
#         try:
#             # Call analyzer function directly - assumes it has a main analysis function
#             if hasattr(self.analyzer, 'analyze_issue'):
#                 analyzer_data = self.analyzer.analyze_issue(github_issue_url)
#             elif hasattr(self.analyzer, 'main'):
#                 analyzer_data = self.analyzer.main(github_issue_url)
#             elif hasattr(self.analyzer, 'run_analysis'):
#                 analyzer_data = self.analyzer.run_analysis(github_issue_url)
#             else:
#                 # Fallback: try to find the main function
#                 main_func = getattr(self.analyzer, 'analyze', None) or getattr(self.analyzer, 'process', None)
#                 if main_func:
#                     analyzer_data = main_func(github_issue_url)
#                 else:
#                     raise AttributeError("No suitable analysis function found in analyzer module")
            
#             logger.info("Analyzer completed successfully")
            
#             # Validate required keys
#             required_keys = ['problem_statement', 'filepath', 'paradigm', 'first_guess']
#             if not isinstance(analyzer_data, dict):
#                 raise ValueError("Analyzer must return a dictionary")
                
#             missing_keys = [key for key in required_keys if key not in analyzer_data]
#             if missing_keys:
#                 raise ValueError(f"Analyzer output missing required keys: {missing_keys}")
                
#             return analyzer_data
            
#         except Exception as e:
#             logger.error(f"Error running analyzer: {str(e)}")
#             raise
    
#     def run_swe_agent(self, github_issue_url: str, analyzer_data: Dict[str, Any]) -> Dict[str, Any]:
#         """
#         Run SWE-Agent with the GitHub issue and analyzer context
        
#         Args:
#             github_issue_url: Original GitHub issue URL
#             analyzer_data: Output from analyzer agent (native Python dict)
            
#         Returns:
#             Dictionary with SWE-Agent results
#         """
#         logger.info("Running SWE-Agent")
        
#         # Create output directory for SWE-Agent
#         swe_output_dir = os.path.join(self.temp_dir, "swe_agent_output")
#         os.makedirs(swe_output_dir, exist_ok=True)
        
#         try:
#             # Build SWE-Agent command
#             cmd = [
#                 sys.executable,
#                 str(self.swe_agent_dir / "sweagent" / "run" / "run.py"),
#                 "run",
#                 "--config", self.swe_config,
#                 "--github-issue", github_issue_url,
#                 "--output-dir", swe_output_dir
#             ]
            
#             # Pass analyzer context as environment variables
#             env = os.environ.copy()
#             env.update({
#                 'ANALYZER_PROBLEM_STATEMENT': str(analyzer_data['problem_statement']),
#                 'ANALYZER_FILEPATH': str(analyzer_data['filepath']),
#                 'ANALYZER_PARADIGM': str(analyzer_data['paradigm']),
#                 'ANALYZER_FIRST_GUESS': str(analyzer_data['first_guess'])
#             })
            
#             # Also save analyzer data as JSON for SWE-Agent to read if needed
#             analyzer_context_file = os.path.join(swe_output_dir, "analyzer_context.json")
#             with open(analyzer_context_file, 'w') as f:
#                 json.dump(analyzer_data, f, indent=2)
#             env['ANALYZER_CONTEXT_FILE'] = analyzer_context_file
            
#             # Run SWE-Agent
#             result = subprocess.run(
#                 cmd,
#                 cwd=self.swe_agent_dir,
#                 capture_output=True,
#                 text=True,
#                 env=env,
#                 check=True
#             )
            
#             logger.info("SWE-Agent completed successfully")
#             logger.debug(f"SWE-Agent stdout: {result.stdout}")
            
#             # Parse SWE-Agent output
#             swe_data = self._parse_swe_agent_output(swe_output_dir, result.stdout)
            
#             # Ensure required keys are present and inherit from analyzer
#             swe_data.update({
#                 'problem_statement': analyzer_data['problem_statement'],
#                 'filepath': analyzer_data['filepath']
#             })
            
#             return swe_data
            
#         except subprocess.CalledProcessError as e:
#             logger.error(f"SWE-Agent failed: {e.stderr}")
#             raise
#         except Exception as e:
#             logger.error(f"Error running SWE-Agent: {str(e)}")
#             raise
    
#     def _parse_swe_agent_output(self, output_dir: str, stdout: str) -> Dict[str, Any]:
#         """
#         Parse SWE-Agent output to extract patch and solution description
        
#         Args:
#             output_dir: SWE-Agent output directory
#             stdout: Standard output from SWE-Agent
            
#         Returns:
#             Dictionary with patch and solution_description
#         """
#         swe_data = {}
        
#         # Look for patch file in output directory
#         patch_files = list(Path(output_dir).glob("*.patch"))
#         if patch_files:
#             with open(patch_files[0], 'r') as f:
#                 swe_data['patch'] = f.read()
#         else:
#             # Try to extract patch from stdout
#             swe_data['patch'] = self._extract_patch_from_stdout(stdout)
        
#         # Extract solution description from stdout or summary file
#         summary_files = list(Path(output_dir).glob("*summary*")) + list(Path(output_dir).glob("*result*"))
#         if summary_files:
#             with open(summary_files[0], 'r') as f:
#                 swe_data['solution_description'] = f.read()
#         else:
#             swe_data['solution_description'] = self._extract_solution_from_stdout(stdout)
        
#         return swe_data
    
#     def _extract_patch_from_stdout(self, stdout: str) -> str:
#         """Extract patch content from stdout"""
#         lines = stdout.split('\n')
#         patch_lines = []
#         in_patch = False
        
#         for line in lines:
#             if line.startswith('diff --git') or line.startswith('---') or line.startswith('+++'):
#                 in_patch = True
#                 patch_lines.append(line)
#             elif in_patch and line.startswith('@@'):
#                 patch_lines.append(line)
#             elif in_patch and (line.startswith('+') or line.startswith('-') or line.startswith(' ')):
#                 patch_lines.append(line)
#             elif in_patch and not line.strip():
#                 patch_lines.append(line)
#             elif in_patch and not any(line.startswith(p) for p in ['+', '-', ' ', '@@']):
#                 in_patch = False
        
#         return '\n'.join(patch_lines) if patch_lines else stdout
    
#     def _extract_solution_from_stdout(self, stdout: str) -> str:
#         """Extract solution description from stdout"""
#         lines = stdout.split('\n')
#         solution_lines = []
        
#         # Simple heuristic: look for lines after "Solution:" or "Summary:"
#         capture = False
#         for line in lines:
#             if any(keyword in line.lower() for keyword in ['solution:', 'summary:', 'completed:', 'result:']):
#                 capture = True
#                 solution_lines.append(line)
#             elif capture:
#                 solution_lines.append(line)
        
#         return '\n'.join(solution_lines) if solution_lines else "Solution completed by SWE-Agent"
    
#     def run_revisor(self, swe_data: Dict[str, Any]) -> Dict[str, Any]:
#         """
#         Run the revisor agent with SWE-Agent output
        
#         Args:
#             swe_data: Output from SWE-Agent (native Python dict)
            
#         Returns:
#             Dictionary with revisor results
#         """
#         logger.info("Running revisor")
        
#         try:
#             # Call revisor function directly - assumes it has a main review function
#             if hasattr(self.revisor, 'review_solution'):
#                 revisor_data = self.revisor.review_solution(swe_data)
#             elif hasattr(self.revisor, 'main'):
#                 revisor_data = self.revisor.main(swe_data)
#             elif hasattr(self.revisor, 'run_review'):
#                 revisor_data = self.revisor.run_review(swe_data)
#             else:
#                 # Fallback: try to find the main function
#                 main_func = getattr(self.revisor, 'review', None) or getattr(self.revisor, 'process', None)
#                 if main_func:
#                     revisor_data = main_func(swe_data)
#                 else:
#                     raise AttributeError("No suitable review function found in revisor module")
            
#             logger.info("Revisor completed successfully")
            
#             if not isinstance(revisor_data, dict):
#                 raise ValueError("Revisor must return a dictionary")
                
#             return revisor_data
            
#         except Exception as e:
#             logger.error(f"Error running revisor: {str(e)}")
#             raise
    
#     def run_pipeline(self, github_issue_url: str) -> Dict[str, Any]:
#         """
#         Run the complete multi-agent pipeline
        
#         Args:
#             github_issue_url: GitHub issue URL to process
            
#         Returns:
#             Dictionary with final results from all agents
#         """
#         logger.info(f"Starting multi-agent pipeline for: {github_issue_url}")
        
#         try:
#             # Step 1: Run Analyzer
#             analyzer_data = self.run_analyzer(github_issue_url)
#             logger.info("✓ Analyzer completed")
            
#             # Step 2: Run SWE-Agent
#             swe_data = self.run_swe_agent(github_issue_url, analyzer_data)
#             logger.info("✓ SWE-Agent completed")
            
#             # Step 3: Run Revisor
#             revisor_data = self.run_revisor(swe_data)
#             logger.info("✓ Revisor completed")
            
#             # Combine all results using native Python dictionaries
#             final_results = {
#                 'github_issue_url': github_issue_url,
#                 'analyzer': analyzer_data,
#                 'swe_agent': swe_data,
#                 'revisor': revisor_data,
#                 'pipeline_status': 'completed'
#             }
            
#             logger.info("Pipeline completed successfully")
#             return final_results
            
#         except Exception as e:
#             logger.error(f"Pipeline failed: {str(e)}")
#             final_results = {
#                 'github_issue_url': github_issue_url,
#                 'pipeline_status': 'failed',
#                 'error': str(e)
#             }
#             return final_results
    
#     def cleanup(self):
#         """Clean up temporary files"""
#         if os.path.exists(self.temp_dir):
#             shutil.rmtree(self.temp_dir)
#             logger.info(f"Cleaned up temporary directory: {self.temp_dir}")

# # Ejemplo de uso programático
# def example_usage():
#     """Ejemplo de cómo usar el orchestrator programáticamente"""
    
#     # Crear el orchestrator
#     orchestrator = MultiAgentOrchestrator(
#         analyzer_module="analyzer.py",
#         revisor_module="revisor.py",
#         swe_agent_dir="SWE-Agent",
#         swe_config="config.yaml"
#     )
    
#     # Ejecutar el pipeline
#     github_issue = "https://github.com/user/repo/issues/123"
#     results = orchestrator.run_pipeline(github_issue)
    
#     # Procesar resultados
#     if results['pipeline_status'] == 'completed':
#         print("Pipeline completado exitosamente!")
#         print(f"Problema: {results['analyzer']['problem_statement']}")
#         print(f"Archivo: {results['analyzer']['filepath']}")
#         print(f"Paradigma: {results['analyzer']['paradigm']}")
#         print(f"LGTM del revisor: {results['revisor'].get('lgtm', False)}")
#     else:
#         print(f"Pipeline falló: {results['error']}")
    
#     # Cleanup
#     orchestrator.cleanup()
    
#     return results

# def main():
#     """Main entry point for CLI usage"""
#     import argparse
    
#     parser = argparse.ArgumentParser(description="Multi-Agent Orchestrator")
#     parser.add_argument("--issue-url", required=True, help="GitHub issue URL")
#     parser.add_argument("--analyzer", default="analyzer.py", help="Path to analyzer.py")
#     parser.add_argument("--revisor", default="revisor.py", help="Path to revisor.py")
#     parser.add_argument("--swe-agent-dir", default="SWE-Agent", help="Path to SWE-Agent directory")
#     parser.add_argument("--swe-config", default="some.yaml", help="SWE-Agent config file")
#     parser.add_argument("--temp-dir", help="Temporary directory for intermediate files")
#     parser.add_argument("--output", help="Output JSON file for final results")
#     parser.add_argument("--keep-temp", action="store_true", help="Keep temporary files")
    
#     args = parser.parse_args()
    
#     # Create orchestrator
#     orchestrator = MultiAgentOrchestrator(
#         analyzer_module=args.analyzer,
#         revisor_module=args.revisor,
#         swe_agent_dir=args.swe_agent_dir,
#         swe_config=args.swe_config,
#         temp_dir=args.temp_dir
#     )
    
#     try:
#         # Run pipeline
#         results = orchestrator.run_pipeline(args.issue_url)
        
#         # Save results if output file specified
#         if args.output:
#             with open(args.output, 'w') as f:
#                 json.dump(results, f, indent=2)
#             print(f"Results saved to: {args.output}")
#         else:
#             print("=== PIPELINE RESULTS ===")
#             if results['pipeline_status'] == 'completed':
#                 print(f"✓ Issue: {results['github_issue_url']}")
#                 print(f"✓ Problem: {results['analyzer']['problem_statement']}")
#                 print(f"✓ File: {results['analyzer']['filepath']}")
#                 print(f"✓ Solution: {results['swe_agent']['solution_description'][:100]}...")
#                 print(f"✓ Review: {results['revisor']}")
#             else:
#                 print(f"✗ Failed: {results['error']}")
            
#     finally:
#         # Cleanup unless requested to keep temp files
#         if not args.keep_temp:
#             orchestrator.cleanup()

# if __name__ == "__main__":
#     main()