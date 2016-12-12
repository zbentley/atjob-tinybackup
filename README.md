# atjob-tinybackup

A tiny single-file-backup program that schedules itself.

This program is a *very* minimal backup utility. It supports:

- Backing up one file per run, to one folder. To back up multiple files, invoke this script multiple times.
- Scheduling itself to run in the future or on an interval.
- Running on Linux, BSD, and OSX.
- Compressing backed up files.
- Keeping and rotating a configurable number of timestamped backups of the target file.

### Goals

- Be easy to use for anyone who can open a terminal.
- Be easy to install: a single script file is all that should be needed.
- Remain as simple as possible. Single files are backed up to single locations.
- Dependencies should be either omnipresent (Python), or very easy to install.
- Should not disturb, lock, or otherwise modify data being backed up.

### Non-Goals

- Multi-file or folder backup. `atjob-tinybackup` is designed to back up single files to a location on a schedule. Schedule as many instances of `atjob-tinybackup` as you like, but if you find yourself needing complex filtering on things to be backed up, or if you need to back up entire directories at a time, you probably need a general-purpose backup tool. [CrashPlan](https://www.crashplan.com) is a good general-purpose solution, and there are many others.
- `cron` or other scheduler integration. The whole point of using `at` for self-scheduling jobs is that jobs aren't added via a central index (like a crontab); they're added by whoever wants them to run, and can be programmatically added, located, and removed. The lack of the ability to easily modify `at` jobs is also desirable; once a job is created, it can only be run or destroyed. If you want to run your backup jobs via another scheduler, like `cron`, OSX Automator, launchd, or the Windows scheduling service, you probably do not want this script. `atjob-tinybackup` is for people that don't want to deal with those systems.
- Scheduling precision greater than ~2 minutes. `at` (the scheduling system used by `atjob-tinybackup`) is a queued job scheduler, so jobs may not be initiated immediately when they are scheduled; unexpected lag may be introduced in addition to the overhead of launching the job in the first place. `at` only supports scheduling jobs to the minute (not, say, to the second or millisecond). Additionally, some crude implementations of `at` (Mac OSX's in particular) will only poll for jobs to launch once every minute or two, regardless of when they are queued.

# Installation

This program has the following runtime requirements:
- A running `atd` process or equivalent invoker of `atrun`. See [`at(1)`](https://linux.die.net/man/1/at) for more info.
- Python (2 or 3; I have tested with 2.6, 2.7, 3.1, and 3.5).
- [`logrotate`](https://linux.die.net/man/8/logrotate).

### OSX

- Install [homebrew](http://brew.sh/).
- Install logrotate: `brew install logrotate`.
- Start the `at` daemon: `sudo launchctl load -w /System/Library/LaunchDaemons/com.apple.atrun.plist`.
	- If that command does not work, open a terminal and type `man atrun` for activation instructions specific to your distribution of OSX.
- Put this script in a stable location. If you move or delete the `tinybackup.py` file in between scheduled backups, all future backups will fail. You can have multiple copies of the script on your system. Many users find it convenient to place a copy of the `tinybackup.py` script in the same folder as the files which they are using it to back up.

# Linux:

Coming soon.

# BSD:

Coming soon (tested working on FreeBSD; I just have to find time to document the install steps).

# Examples


Back up `myfile.txt` in the current user's home directory (`/Users/username` on Mac OSX) into the `mydir` directory in the current user's home directory. Run one backup immediately, and another one at 2:00am every day in the future:

```
python tinybackup.py --sourcefile ~myfile.txt --destinationdirectory ~mydir/ --install --run --time '2:00am'
```


Remove (unschedule all future occurrences of) the backup scheduled in the example above:
```
python tinybackup.py --sourcefile ~myfile.txt --destinationdirectory ~mydir/ --uninstall --time '2:00am'
```

Run a single backup (do not schedule any future backups) of the file `/Users/maggie/Dropbox/somefile.pdf` to the directory `/Users/maggie/backupfolder/`:

```
python tinybackup.py --sourcefile /Users/maggie/Dropbox/somefile.pdf --destinationdirectory /Users/maggie/backupfolder --run'
```

Examine all scheduled backups on the system:

```
python tinybackup.py --sourcefile /Users/maggie/Dropbox/somefile.pdf --destinationdirectory /Users/maggie/backupfolder --statusof all'
```

Remove all scheduled backups using the same source file and destination directory, regardless of when they are scheduled:

```
python tinybackup.py --sourcefile /Users/maggie/Dropbox/somefile.pdf --destinationdirectory /Users/maggie/backupfolder --uninstall "jobs with this source and destination"'
```

# Usage

```
python tinybackup.py (--install | --uninstall JOB_FILTER | --statusof JOB_FILTER)
                     [--run] [--time TIME] [--keeprevisions REVISIONS]
                     --sourcefile SOURCEFILE --destinationdirectory
                     DESTINATIONDIRECTORY [--debug] [--noop]

Schedule a repeated backup of a single file.

optional arguments:
  -h, --help            show this help message and exit
  --install, -i         Schedule this script to run repeatedly at a given
                        time.
  --uninstall JOB_FILTER, -u JOB_FILTER
                        Remove all scheduled runs of this script for a given
                        SOURCEFILE and DESTINATIONDIRECTORY
  --statusof JOB_FILTER, -s JOB_FILTER
                        Display all already-scheduled runs of this script for
                        a given SOURCEFILE and DESTINATIONDIRECTORY
  --run, -r             Run a backup immediately, in addition to any other
                        actions taken.
  --time TIME, -t TIME  Time in the future to schedule (or uninstall) backup
                        jobs
  --keeprevisions REVISIONS, -k REVISIONS
                        How many backups of the file to keep. Old ones will be
                        rotated out.
  --sourcefile SOURCEFILE, -f SOURCEFILE
                        File to back up.
  --destinationdirectory DESTINATIONDIRECTORY, --destdir DESTINATIONDIRECTORY, -d DESTINATIONDIRECTORY
                        Directory in which to store backed up files.
  --debug               Enable debug output.
  --noop                Do scheduling and job installation as normal, but do
                        not actually create any backups; write diagnostic
                        output instead.
```

For detailed commandline usage and help information, do `tinybackup.py --help`. A summary of commandline usage is provided below:

`atjob-tinybackup` has four main modes of operation, one of which is required when invoking `tinybackup.py`:
- **`--run` mode** immediately executes a backup of a specified file to a specified directory.
- **`--install` mode** schedules the script to execute itself (i.e. to do the operations of `--run` mode) on a schedule.
- **`--uninstall` mode** removes instances of this script that were previously scheduled with `--install` mode.
- **`--statusof` mode** displays instances of this script that have been scheduled with `--install` mode.

`--run` mode can be combined with `--install` mode (to take an initial backup and schedule future backups in one invocation), but cannot be combined with any other modes.

Once you have selected a mode, you must select a source file and destination directory, via the `--sourcefile` and `--destinationdirectory` parameters. 

To simply perform a backup operation once, you can do `tinybackup.py --sourcefile /path/to/file --destinationdirectory /path/to/destination/dir/ --run`.

The `--install` mode and `--uninstall` mode may require a `--time` argument to function; see the "Time Specifications" section below for more info.

### Time Specifications

When scheduling an instalce of `atjob-tinybackup`, it needs to know when in the future to run (or, in the case of `--uninstall`, what schedule of jobs to uninstall). `atjob-tinybackup` accepts any time specification accepted by [`at(1)`](https://linux.die.net/man/1/at). For example, the following can be supplied to the `--time` argument:

- `00:00`: run at midnight.
- `'3:00pm 4/27' run at 3pm on April 27th.
- `'15:00 4/27' run at 3pm ([1500 hours](https://en.wikipedia.org/wiki/24-hour_clock)) on April 27th.
- `'+1day'`: run 1 day after this.
- `'+7 minutes'`: run 7 minutes after this. 
- `'3:00 +1 year': run 1 year from now, at 3am.
- `teatime`: run at 4:00pm.

For more examples, see `man at` on your system, or [this excellent article on the formats supported by `at`](http://www.computerhope.com/unix/uat.htm).

Time specifications relative to the time the user runs `tinybackup.py` are available. For example, `--time +1hour` will run the backup job approximately one hour from when the command is entered, and again one hour after that, and so on. Using multiple backup jobs with the same absolute or relative time specification (regardless of when they actually _run_) may result in unexpected behavior; see the "Limitations" section below for more info.

`atjob-tinybackup` will reject invalid time specifications. If you aren't sure whether a time specification is valid, try using it to schedule a backup job of an empty file (for example, `/dev/null`), or schedule a backup and then immediately unschedule (`--uninstall`) it.

### Absolute and Relative Paths

Regardless of how they are supplied to `tinybackup.py`, all paths are treated as absolute, and are "frozen" when the first backup is scheduled. `tinybackup.py --sourcefile ../myfile.txt --install --time +1day` will only ever back up the file called `myfile.txt` in the directory above the one in which `tinybackup.py` was run by the user. If `tinybackup.py` or the file are moved, the backup process will not change.

### Job Filters

When using the `--statusof` or `--uninstall` flags, it is necessary to specify what jobs you are interested in. For example, if you have a handful of `atjob-tinybackup` jobs scheduled on a machine and one of them has become pointless, it would be a hassle to have to uninstall all of them and then reinstall all except the pointless one. In support of that, `tinybackup.py` supports a handful of "job filter" criteria that can be used to identify a particular job. 

The below criteria are valid arguments (case insensitively) to `--statusof` or `--uninstall`:

- `all backup jobs`, `all`, or `queue`: Operate on all jobs created in the `at` queue used by `atjob-tinybackup`. Note that this is **not** the default queue used when scheduling jobs manually via `echo job... | at ...`.
- `jobs with this source and destination`, `files`, `same files`: Operate on jobs with the same (absolute, not relative) `--sourcefile` and `--destinationdirectory` arguments. Additionally implies the `all backup jobs` filter (filters are _AND_ed together).
- `jobs exactly like this one`, `jobs just like this one`, `jobs identical to this one`, `this`, `this job`, `this time`, `time`: Operate on jobs with the same `--time` string as is supplied to whatever mode (e.g. `--install --time +1day`) is being used. Additionally implies the `jobs with this source and destination` filter (filters are _AND_ed together). See the "Limitations" section for more info.

# Limitations

- On some systems (Solaris and Linux that I know of; BSDs may have something similar), the `at.allow` and `at.deny` files can be used to permit or deny users ability to use the `at` job scheduler. If a user wishing to use `atjob-tinybackup` is not permitted to use the scheduler via those two files, they can only use this script in `--run` mode; no other modes will work in a useful way.
- If two jobs scheduled by `--install` happen to occur at the same time but were not scheduled with the same value for the `--time` parameter (e.g. if one is scheduled every minute with `--time '+1 minute'` and one is scheduled on the hour at 2:00AM with `--time '2:00'`), the two jobs will run simultaneously. Similarly, `--uninstall`ing one job will not uninstall the other. This applies _even if two jobs are scheduled with equivalent schedules that are only **textually** different_, for example `--time +2day` and `--time '+ 2 days'`.
- If two jobs are scheduled with the same source and destination, and same relative time string (e.g. `--time 'now + 1 day'`), they will be removed by any `--uninstall "jobs exactly like this one"` command, _regardless of when the user ran the commands to schedule both jobs_. For example, if a user scheduled one job with `--time +1day` at noon, and scheduled another, identical job at midnight, `--uninstall --time +1day` would destroy both jobs. This can be worked around by using absolute, rather than relative, time strings; in this example, one job would be scheduled with `--time 00:00` and another with `--time 12:00`. 
- Behavior when a system is shut down, asleep, has a stopped `at` daemon or equivalent, or is otherwise not running jobs, is currently undefined. Jobs may run after the system starts back up, or they may not. Behavior in these cases is left up to `at`; check your system's implementation information for more info via `man at`.

# FAQ

Q: Something isn't working; my backups won't run when scheduled, and I don't know why. What can I do to figure out what's wrong?
A: Run `tinybackup.py` with the `--debug` argument to see what it's doing when it runs on schedule. That argument will cause it to write its output to a file called `debug.txt` in _the directory in which you invoked `tinybackup.py`. For example, if you did `cd /home/me; ./mypath/tinybackup.py ... --debug`, output would be written to `/home/me/debug.txt`. If that doesn't help you fix the issue, follow the instructions in the "Bugs/Contributing" section below.

Q: I don't have this script installed any more, but backup jobs are still running? How can I turn them off?
A: Run `at -l -q z | cut -f1 | xargs at -r` to remove jobs scheduled by this version of `atjob-tinybackup` from your system. Run `at -l | cut -f1 | xargs at -r` to remove all scheduled jobs on your system.

Q: What if I just want to run one backup at some point in the future, but don't want them to keep reoccurring after that until I uninstall them?
A: Just use `at` directly. Take whatever time-string you'd supply to `--install` if you wanted to schedule the script to run in the future, and supply it to `at` and `echo` a `--run`-mode invocation of `atjob-tinybackup` to it, like so:
```
echo python3 tinybackup.py --sourcefile /path/to/file --destdir /path/to/dir/ --run | at "+2 days"
```

Q: Can I use `atjob-tinybackup` inside a larger Pyhton program?
A: Not directly. You'll have to shell out and run it. Parts of the scheduling system only work because the entire program is in a single, executable Python script. You can `import` the `tinybackup.py` file, but it probably won't work the way you want it to unless run directly.

Q: How can I integrate `atjob-tinybackup` with my existing scheduler or backup system?
A: `atjob-tinybackup` should generally be used with its own (`at`-bases) scheduling. If you want to schedule it or run it as part of another script, you can use `tinybackup.py ... --run` mode to just execute a backup, and not do any scheduling. In that case, however, you might be better off just using `logrotate` directly to run your backups; `tinybackup.py` doesn't add much. See [the `logrotate` documentation](https://linux.die.net/man/8/logrotate) for more info.

# Bugs/Contributing

File an issue or pull request on [the GitHub repository for this project](https://github.com/zbentley/atjob-tinybackup).

When filing an issue, please run the `tinybackup.py` script with the parameters that are causing the bug, and additionally the `--debug` and `--noop` flags. Debug output will be written to `debug.txt` in the directory where you invoked `tinybackup.py`. Please also include as many details about your host system and the files you are working with as possible.