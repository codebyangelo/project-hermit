import os
import sys
import datetime

# Resolve log path relative to this script's directory
EXECUTION_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "execution.log")

class ExecutionLogger:
    TOTAL_PROMPT_TOKENS = 0
    TOTAL_COMPLETION_TOKENS = 0

    @staticmethod
    def add_tokens(prompt_tokens: int, completion_tokens: int):
        ExecutionLogger.TOTAL_PROMPT_TOKENS += prompt_tokens
        ExecutionLogger.TOTAL_COMPLETION_TOKENS += completion_tokens

    @staticmethod
    def rotate_logs():
        # Compress execution.log if size > 10MB
        if os.path.exists(EXECUTION_LOG_PATH):
            try:
                if os.path.getsize(EXECUTION_LOG_PATH) > 10 * 1024 * 1024: # 10MB
                    import gzip
                    import shutil
                    # Keep last 3 runs: execution.log.1.gz, execution.log.2.gz, execution.log.3.gz
                    for i in range(3, 0, -1):
                        old_archive = os.path.join(os.path.dirname(EXECUTION_LOG_PATH), f"execution.log.{i}.gz")
                        if os.path.exists(old_archive):
                            if i == 3:
                                os.remove(old_archive)
                            else:
                                new_archive = os.path.join(os.path.dirname(EXECUTION_LOG_PATH), f"execution.log.{i+1}.gz")
                                os.rename(old_archive, new_archive)
                    # Write current log to compressed file
                    archive_name = os.path.join(os.path.dirname(EXECUTION_LOG_PATH), "execution.log.1.gz")
                    with open(EXECUTION_LOG_PATH, 'rb') as f_in:
                        with gzip.open(archive_name, 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    # Clear original log
                    open(EXECUTION_LOG_PATH, 'w').close()
            except Exception as e:
                print(f"[!] Logger Rotation Error: {e}")

    @staticmethod
    def log(component: str, message: str, level: str = "INFO"):
        ExecutionLogger.rotate_logs()
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        formatted = f"[{timestamp}] [{level}] [{component}] {message}"
        
        # Print to terminal with basic ANSI colors for transparency
        if level == "ERROR" or level == "CRITICAL":
            print(f"\033[91m{formatted}\033[0m")
        elif level == "WARN":
            print(f"\033[93m{formatted}\033[0m")
        elif level == "SUCCESS":
            print(f"\033[92m{formatted}\033[0m")
        else:
            print(formatted)
            
        # Append to execution log
        try:
            with open(EXECUTION_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(formatted + "\n")
        except Exception as e:
            # Fallback if logging fails
            print(f"[!] Logger IO Error: {e}")
