Overview
The TMH project is a well-structured iron ore metallurgical testing and control system built with PySide6, featuring real-time multi-device data acquisition, experiment management, and data analysis. The architecture is solid with clear layer separation. Below are prioritized improvement suggestions.

1. CRITICAL: Security — Password Management
File: src/utils/password_manager.py
Problem: Passwords are stored and compared in plaintext. Default password "1952" is hardcoded. The JSON config file stores raw passwords.
Suggestion:

Hash passwords using hashlib.pbkdf2_hmac or bcrypt before storage
Store only the hash + salt in the config file
Use secrets.compare_digest() for constant-time comparison to prevent timing attacks
Remove the hardcoded default password; force first-time setup instead

python# Example approach:
import hashlib, secrets

def hash_password(password: str, salt: bytes = None) -> tuple[str, str]:
    salt = salt or secrets.token_bytes(16)
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    return hashed.hex(), salt.hex()

def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 100000)
    return secrets.compare_digest(hashed.hex(), stored_hash)

2. HIGH: Error Handling — Replace print() with Logger
Files: src/services/experiment_file.py (lines 50, 69, 88, 131, 165, 203, 271, 280), src/utils/password_manager.py (lines 25, 34)
Problem: These files use print() for error reporting instead of the project's logger. In a packaged/production application, print output is lost.
Suggestion: Replace all print(f"...") calls with logger.error(...) using the existing get_logger() utility.

3. HIGH: Error Handling — Overly Broad Exception Catching
Files: src/services/database.py (lines 187, 202, 220, 250, 278, 306, 336, 355), src/device_clients/data_handler.py (lines 82, 149, 204, 214, 236, 274)
Problem: Many methods catch bare Exception when more specific exception types should be used. This masks bugs and makes debugging harder.
Suggestion:

In database code: catch sqlite3.Error specifically (already done partially at line 181-186, apply consistently)
In device code: catch serial.SerialException, TimeoutError, ValueError as appropriate
Keep a final except Exception only at the outermost layer (e.g., thread loops) as a safety net


4. HIGH: Thread Safety Issues
File: src/device_clients/multi_mfc_client.py:31
Problem: self._last_values dict is written from the data collection thread and read from UI/status threads without any synchronization.
File: src/device_clients/data_handler.py:165
Problem: Directly accesses private self.device_manager._devices[name] — breaks encapsulation and is unsafe if devices are added/removed concurrently.
Suggestion:

Add a threading.Lock to protect _last_values in MultiMFCClient
Add a public get_device(name) method to DeviceManager instead of accessing _devices directly


5. HIGH: Dataclass Mutable Default Values
File: src/services/database.py:30-34
Problem: ExperimentData dataclass uses None defaults for mutable fields (List, Dict) then assigns in __post_init__. While functional, this is fragile and not idiomatic.
Suggestion: Use field(default_factory=...):
pythonfrom dataclasses import dataclass, field

timestamps: List[str] = field(default_factory=list)
temperatures: List[float] = field(default_factory=list)
gas_flows: Dict[str, List[float]] = field(default_factory=lambda: {"CO": [], "CO2": [], "N2": [], "H2": []})

6. MEDIUM: Incomplete/Stub Implementations
File: src/services/experiment_file.py:225-234
Problem: _generate_pdf_report(), _generate_docx_report(), and _generate_xlsx_report() are stub methods that silently return None (not False). The caller generate_report() will treat None as success not being False.
Suggestion:

Either implement them or raise NotImplementedError
If intentionally deferred, at least return False and log a warning


7. MEDIUM: Magic Numbers and Hardcoded Values
Files and examples:

src/device_clients/multi_mfc_client.py:124 — int(value * 10) (protocol scaling factor) — add a named constant MFC_SCALE_FACTOR = 10
src/device_clients/data_handler.py:38-40 — 0.5 and 5.0 for intervals/timeouts — already loaded from config but fallback values should be named constants
src/services/database.py:55-60 — ExperimentConfig defaults (900.0, 10.0, 180) — document units in field names or comments
src/utils/logger.py — 10*1024*1024 for log size — use a named constant MAX_LOG_FILE_SIZE = 10 * 1024 * 1024


8. MEDIUM: Database Query Fragility
File: src/services/database.py:293-304
Problem: get_experiment_data() uses positional indexing (row[2], row[3], etc.) with defensive len(row) > N checks. This is brittle and will break if columns are reordered.
Suggestion: Use conn.row_factory = sqlite3.Row to get dict-like access:
pythonconn.row_factory = sqlite3.Row
# Then: row['timestamp'], row['temperature'], etc.

9. MEDIUM: Command Parsing Without Validation
File: src/device_clients/multi_mfc_client.py:165-169
Problem: send_command() uses cmd.split(":")[1] without bounds checking. If someone passes "read:" (no gas name), this returns an empty string and causes a confusing error.
Suggestion: Validate the split result:
pythonparts = cmd.split(":", 1)
if len(parts) < 2 or not parts[1]:
    raise ValueError(f"Invalid command format: {cmd}")
gas = parts[1]
```

---

## 10. LOW: Dependency Versioning

**File:** `requirements.txt`

**Problem:** Dependencies use only `>=` without upper bounds. A future major version bump (e.g., PySide6 7.x, NumPy 2.x) could break the application silently.

**Suggestion:** Add upper version caps:
```
PySide6>=6.9.0,<7.0.0
numpy>=1.24.0,<3.0.0
pandas>=2.0.0,<3.0.0
Also consider adding a requirements-dev.txt for development-only dependencies (pytest, black, flake8, mypy).

11. LOW: Typo in Filename
File: src/utils/jason_manager.py
Problem: File is named jason_manager.py — likely should be json_manager.py.

12. LOW: Inconsistent Logging — Emojis in Debug Logs
File: src/device_clients/data_handler.py:209
Problem: Debug log uses emoji 📡 Snapshot: — this can cause encoding issues in some log handlers and is inconsistent with the rest of the codebase.
Suggestion: Remove emojis from log messages and use plain text.

13. LOW: Lazy Imports Inside Functions
File: src/services/experiment_file.py:93, 171
Problem: import csv and import pandas as pd are imported inside functions. While the pandas lazy import is reasonable (heavy dependency), csv is stdlib and should be at the top.
Suggestion: Move import csv to the top of the file. Keep pandas as lazy import but add a comment explaining why.

14. LOW: Git Commit Message Quality
Problem: Recent commit history shows inconsistent formats: "udapte" (typo), "first commit" (vague), garbled characters. The project's CONTRIBUTING.md already specifies conventional commit format.
Suggestion: Enforce conventional commit format going forward: feat:, fix:, docs:, refactor:, test:, etc. Consider adding a commit-msg git hook.

Priority Summary
#SeverityIssueEffort1CRITICALPlaintext password storageSmall2HIGHprint() instead of loggerSmall3HIGHOverly broad exception catchingMedium4HIGHThread safety (_last_values, _devices)Small5HIGHDataclass mutable defaultsSmall6MEDIUMStub methods silently return NoneSmall7MEDIUMMagic numbers lacking constantsMedium8MEDIUMPositional row indexing in DB queriesSmall9MEDIUMCommand parsing without validationSmall10LOWDependency version capsSmall11LOWTypo in filename (jason_manager)Small12LOWEmojis in log messagesSmall13LOWLazy stdlib importsSmall14LOWGit commit message qualityOngoing

Verification
After implementing changes:

Run existing test suite: pytest tests/ -v
Run type checker: mypy src/
Run linter: flake8 src/ --max-line-length 120
Verify password hashing works by running the app and testing login
Verify device communication still works with fake device server
Check that all log output goes to log files (no stray print() calls)