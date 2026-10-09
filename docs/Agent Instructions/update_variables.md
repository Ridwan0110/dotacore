## Instruction Title: Update VARIABLES.md

---

## Pre-execution Instructions

Ignore `tests` directory on the project root or any test_*/pytest files.

Verify a `.md` or `VARIABLES.md` file has been provided alongside the instruction. If not given, ask for a path where that file should be created.

Follow this structure to update the file:

```markdown
# VARIABLES.md

This file documents all the variables (including environment) that is used as config in the application.

# Config Variables:

## Required Config Variables:
- `API`: URL of the API endpoint

## Optional Config Variables
> **NOTE:** No optional config variables are present

# Environment Variables:

## Required Environment Variables
- `API` (common): URL of the API endpoint

## Optional Environment Variables
- `TIMEZONE`: Time zone to correctly log timestamps
```

### Definitions

1. **Config Variables:** Any data that may be read/write from/to a file and used in the application runtime are considered config variables.
2. **Required Config Variables:** Any config variable that is required to have a value for the application to run properly.
3. **Optional Config Variables:** Any config variable that is not required to have a value for the application to run properly.
4. **Environment Variables:** Any data that may be read from application environment are considered environment variables.
5. **Required Environment Variables:** Any environment variable that is required to have a value for the application to run properly.
6. **Optional Environment Variables:** Any environment variable that is not required to have a value for the application to run properly.
7. **Common Variables:** Any variable that may appear in both config and environment variables are considered common variables. In that case, environment variables will get priority in the application.

## Execution Instructions

### Step 1:
Read and understand these from the provided `.md` file:

- How many variables are documented there
- How many common variables are there between config and environment

Keep these data in your memory

## Step 2:
Read `AGENTS.md` from the project root if not already. Then search every code file for both config and environment variables.
Create a list of every matching variables and categorize them accordingly.

## Step 3:
Search for any variables that is already documented. Keep the documented variables in a separate list.

Document other non-documented variables in their respective category on the `.md` file.

## Step 4:
Get back to list of the already documented variables. Understand what are documented about those variables.
Then verify those variables still work like they are documented. If found any mismatch, keep the variable names alongside how they are mismatched to a mismatched documented variables list.

## Step 5:
If there is any mismatched documented variables, prompt the user about those mismatch and ask for permission if you should fix the documentation.
