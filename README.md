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
- Scheduling precision greater than ~2 minutes. `at` (the scheduling system used by `atjob-tinybackup`) is a queued job scheduler, so jobs may not be initiated immediately when they are scheduled; unexpected lag may be introduced in addition to the overhead of launching the job in the first place. `at` only supports scheduling jobs to the minute (not, say, to the second or millisecond). Additionally, some crude implementations of `at` (Mac OSX's in particular) will only poll for jobs to launch once every minute or two, regardless of when they are queued.

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

For detailed commandline usage and help information, do `tinybackup.py --help`. A summary of commandline usage is provided below:

`atjob-tinybackup` has four main modes of operation, one of which is required when invoking `tinybackup.py`:
- **`--run` mode** immediately executes a backup of a specified file to a specified directory.
- **`--install` mode** schedules the script to execute itself (i.e. to do the operations of `--run` mode) on a schedule.
- **`--uninstall` mode** removes instances of this script that were previously scheduled with `--install` mode.
- **`--statusof` mode** displays instances of this script that have been scheduled with `--install` mode.

`--run` mode can be combined with `--install` mode (to take an initial backup and schedule future backups in one invocation), but cannot be combined with any other modes.



### Time Specifications

### Absolute and Relative Paths

### Job Identification Levels

# Examples

# Limitations

- On some systems (Solaris and Linux that I know of; BSDs may have something similar), the `at.allow` and `at.deny` files can be used to permit or deny users ability to use the `at` job scheduler. If a user wishing to use `atjob-tinybackup` is not permitted to use the scheduler via those two files, they can only use this script in `--run` mode; no other modes will work in a useful way.
- If two jobs scheduled by `--install` happen to occur at the same time but were not scheduled with the same value for the `--time` parameter (e.g. if one is scheduled every minute with `--time '+1 minute'` and one is scheduled on the hour at 2:00AM with `--time '2:00'`), the two jobs will run simultaneously. Similarly, `--uninstall`ing one job will not uninstall the other. This applies _even if two jobs are scheduled with equivalent schedules that are only **textually** different_, for example `--time +2day` and `--time '+ 2 days'`.
- The opposite of that scenario is also true. If two jobs are scheduled with the same relative time string (e.g. `--time 'now + 1 day'`), they will be removed by any `--uninstall "jobs exactly like this one"` command, _regardless of when the user ran the commands to schedule both jobs_. For example, if a user scheduled one job with `--time +1day` at noon, and scheduled another, identical job at midnight, `--uninstall --time +1day` would destroy both jobs. 
- Behavior when a system is shut down, asleep, has a stopped `at` daemon or equivalent, or is otherwise not running jobs, is currently undefined. Behavior in these cases is left up to `at`; check your system's implementation information for more info via `man at`.

# FAQ

- Something isn't working; my backups won't run when scheduled, and I don't know why. What can I do to figure out what's wrong?
- I don't have this script installed any more, but backup jobs are still running? How can I turn them off?
- What if I just want to run one backup at some point in the future, but don't want them to keep reoccurring after that until I uninstall them?

# Bugs/Contributing

File an issue on [the GitHub repository for this project](https://github.com/zbentley/atjob-tinybackup). When filing an issue, please run the `tinybackup.py` script with the parameters that are causing the bug, and additionally the `--debug` flag. Debug output will be written to `debug.txt` in the directory where you invoked `tinybackup.py`. Please also include as many details about your host system and the files you are working with as possible.