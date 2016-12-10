# atjob-tinybackup

A tiny single-file backup program that schedules itself

This program is a *very* minimal backup utility. It supports:

- Backing up one file, per invocation, to one folder. To back up multiple files, simply invoke this script multiple times.
- Scheduling itself to run in the future or on an interval.
- Running on Linux, BSD, and OSX.
- Compressing backed up files.
- Keeping and rotating a configurable number of timestamped backups of the target file.

### Goals

- Easy to use for anyone who can open a terminal.
- Remain as simple as possible. Single files are backed up to single locations.
- Dependencies should be either omnipresent (Python), or very easy to install.
- Should not disturb, lock, or otherwise modify data being backed up.


### Non-Goals

- Multi-file or folder backup. `atjob-tinybackup` is designed to back up single files to a location on a schedule. Schedule as many instances of `atjob-tinybackup` as you like, but if you find yourself needing complex filtering on things to be backed up, or if you need to back up entire directories at a time, you probably need a general-purpose backup tool. [CrashPlan](https://www.crashplan.com) is a good general-purpose solution, and there are many others.
- `cron` or other scheduler integration. The whole point of using `at` for self-scheduling jobs is that jobs aren't added via a central index (like a crontab); they're added by whoever wants them to run, and can be programmatically added, located, and removed. The lack of the ability to easily modify `at` jobs is also desirable; once a job is created, it can only be run or destroyed. If you want to run your backup jobs via another scheduler, like `cron`, OSX Automator, launchd, or the Windows scheduling service, you probably do not want this script. `atjob-tinybackup` is for people that don't want to deal with those systems.

# Installation

This program has the following runtime requirements:
- A running `atd` process. See [`at(1)`](https://linux.die.net/man/1/at) for more info.
- Python (2 or 3; I have tested with 2.6, 2.7, 3.1, and 3.5).
- [`logrotate`](https://linux.die.net/man/8/logrotate).

### OSX
- Install [homebrew](http://brew.sh/).
- Install logrotate: `brew install logrotate`.
- Start the `at` daemon: `sudo launchctl load -w /System/Library/LaunchDaemons/com.apple.atrun.plist`.
	- If that command does not work, open a terminal and type `man atrun` for activation instructions specific to your distribution of OSX.
- Put this script in a stable location. If you move or delete the `tinybackup.py` file in between scheduled backups, all future backups will fail. You can have multiple copies of the script on your system. Many users find it convenient to place a copy of the `tinybackup.py` script in the same folder as the files which they are using it to back up.

# Usage

# Examples

# Bugs/Contributing

File an issue on [the GitHub repository for this project](https://github.com/zbentley/atjob-tinybackup).