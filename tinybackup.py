#!/usr/bin/env python

import argparse
import os
import subprocess
import re
import hashlib
import tempfile
import logging
import sys
import functools
import inspect
# http://stackoverflow.com/questions/967443
try:  # py3
    from shlex import quote
except ImportError:  # py2
    from pipes import quote

# Constants
QUEUE = 'z'
ALL_JOBS = "all backup jobs"
ID_LEVELS = [
	[],
	[ALL_JOBS, "all", "queue"],
	["jobs with this source and destination", "files", "same files"],
	["jobs exactly like this one", "jobs just like this one", "jobs identical to this one", "this", "this job", "this time", "exact", "identical", "time"]
]

def logger(_logger=None):
	if not hasattr(logger, "value"):
		# Silly class to allow info messages printed by this script to not get
		# stamped: http://stackoverflow.com/questions/1343227
		class NonInfoStampedFormatter(logging.Formatter):
			info_fmt = logging.Formatter('%(message)s ')
			other_fmt = logging.Formatter('%(levelname)s in %(name)s: %(message)s')
			def format(self, record):
				if record.levelno == logging.INFO:
					return self.info_fmt.format(record)
				else:
					return self.other_fmt.format(record)
		ch = logging.StreamHandler(sys.stdout)
		ch.setFormatter(NonInfoStampedFormatter())
		loggerinst = logging.getLogger(__file__)
		loggerinst.addHandler(ch)
		loggerinst.setLevel(logging.INFO)
		loggerinst.propagate = False
		logger.value = loggerinst
	return logger.value

def i(msg):
	return logger().info(msg)

def default_errfunc(message):
	raise ValueError(message)

def positive_int(value, errfunc=default_errfunc):
	ivalue = 0
	try:
		ivalue = int(value)
	except ValueError:
		pass
	if ivalue <= 0:
		errfunc("'{}' is an invalid value; must be >= 0".format(value))
	return str(ivalue)

# We won't use argparse's FileTypes, since they allow STDIN to be used, which
# messes up our ability to do fingerprinting.
def readable_file(value, errfunc=default_errfunc):
	if os.path.isfile(value) and os.access(value, os.R_OK):
		return os.path.realpath(value)
	else:
		errfunc("'{}' is not a readable file".format(value))

def writable_dir(value, errfunc=default_errfunc):
	if os.path.isdir(value) and os.access(value, os.W_OK):
		return os.path.realpath(value)
	else:
		errfunc("'{}' is not a writable directory".format(value))

def identity_level(value, errfunc=default_errfunc):
	value = value.lower()
	for idx, level in enumerate(ID_LEVELS):
		if value in level:
			return idx
	uninstinfo = "Invalid value '{}' for --uninstall. Valid values and their roles are:\n".format(value)
	for level in ID_LEVELS[1:]:
		uninstinfo += "Uninstall {}: {}\n".format(level[0], ', '.join('"{0}"'.format(w) for w in level))

	errfunc(uninstinfo.rstrip())

# Validates a timespec with "at". This could technically be done by just calling
# "at" with no STDIN, waiting for a bit, and seeing if it exited with an error
# or just hung waiting for input, but that requires thinking about timeouts, and
# loses us the ability to get the at-formatted timestamp back for examination.
def valid_atjob_timespec(timespec, errfunc=default_errfunc):
	try:
		jobnum, timestring = add_atjob("/bin/true", timespec)
	except subprocess.CalledProcessError as e:
		errfunc(e.output.strip())
	else:
		try:
			remove_atjob(jobnum)
		except subprocess.CalledProcessError as e:
			errfunc(e.output.strip())
	return {
		"parsed": timestring,
		"original": timespec
	}

def remove_atjob(num):
	# Never outputs or changes exit code, even in error.
	return subprocess.check_call(["at", "-r", str(num)])

def get_atjobs_with_string(string):
	jobs = []
	for line in subprocess.check_output(["at", "-l", "-q", QUEUE]).decode('ascii').split("\n"):
		line = line.strip()
		if line:
			line = line.split()
			job = line.pop(0)
			jobtext = subprocess.check_output(["at", "-c", job]).decode('ascii')
			if string in jobtext:
				job = {
					"id": job,
					"schedule": " ".join(line).strip(),
					"command": jobtext,
				}
				logger().debug("found job: " + str(job))
				jobs.append(job)
	return jobs

def add_atjob(cmd, timespec, debug=False):
	oldenv = os.environ.pop("ATJOB_TINYBACKUP_SCRIPT", None)
	r, w = os.pipe()
	os.write(w, cmd.encode())
	os.close(w)

	output = subprocess.check_output(["at", "-q", QUEUE, timespec], stdin=r, stderr=subprocess.STDOUT).decode('ascii')
	matches = re.search("job (\d+) at(.+)", str(output))
	if not (matches and matches.group(1) and matches.group(2)):
		raise subprocess.CalledProcessError(1, "Couldn't get job info after successful installation of '{}'".format(cmd))
	if oldenv:
		os.environ["ATJOB_TINYBACKUP_SCRIPT"] = oldenv
	return (int(matches.group(1).strip()), matches.group(2).strip())

def verify_exe(cmd):
	try:
		# We use -l since --help is noncompliant and returns 1
		subprocess.check_call(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	except:
		logger().error("Could not invoke '{}'; this script cannot function".format(cmd[0]))
		raise

def parse_args():
	# We use -l since --help is POSIX-noncompliant and returns 1
	verify_exe(["at", "-l"])
	verify_exe(["logrotate", "--help"])
	# Global vars

	parser = argparse.ArgumentParser(description='Schedule a repeated backup of a single file.')

	operations = parser.add_mutually_exclusive_group()
	operations.add_argument(
		'--install','-i',
		action='store_true',
		help='Schedule this script to run repeatedly at a given time.'
	)
	operations.add_argument(
		'--uninstall', '-u',
		metavar="JOB_FILTER",
		type=functools.partial(identity_level, errfunc=parser.error),
		help='Remove all scheduled runs of this script for a given SOURCEFILE and DESTINATIONDIRECTORY'
	)
	operations.add_argument(
		'--statusof', '-s',
		metavar="JOB_FILTER",
		type=functools.partial(identity_level, errfunc=parser.error),
		help='Display all already-scheduled runs of this script for a given SOURCEFILE and DESTINATIONDIRECTORY'
	)

	parser.add_argument(
		'--run', '-r',
		action='store_true',
		help='Run a backup immediately, in addition to any other actions taken.'
	)
	parser.add_argument(
		'--time', '-t',
		type=functools.partial(valid_atjob_timespec, errfunc=parser.error),
		help="Time in the future to schedule (or uninstall) backup jobs"
	)
	parser.add_argument(
		'--keeprevisions', '-k',
		metavar='REVISIONS',
		type=positive_int,
		default="14",
		help='How many backups of the file to keep. Old ones will be rotated out.'
	)
	parser.add_argument(
		'--sourcefile', '-f',
		type=functools.partial(readable_file, errfunc=parser.error),
		metavar='SOURCEFILE',
		help='File to back up.',
	)
	parser.add_argument(
		'--destinationdirectory', '--destdir', '-d',
		type=functools.partial(writable_dir, errfunc=parser.error),
		metavar='DESTINATIONDIRECTORY',
		help='Directory in which to store backed up files.',
	)
	parser.add_argument(
		'--debug',
		action='store_true',
		help='Enable debug output.'
	)
	parser.add_argument(
		'--noop',
		action='store_true',
		help='Do scheduling and job installation as normal, but do not actually create any backups; write diagnostic output instead.'
	)

	parser.add_argument('--identifier', help=argparse.SUPPRESS)

	args = parser.parse_args()

	# Do some more complex argument validation: --time is required with --install,
	# and also with --uninstall/status "jobs exactly like this one". Elsewhere it is
	# meaningless.
	timelevelname = ID_LEVELS[identity_level("this")][0]
	if args.uninstall or args.statusof:
		formattpl = (args.uninstall, "uninstall")
		if args.statusof:
			formattpl = (args.statusof, "statusof")
		if formattpl[0] is identity_level("this"):
			if not args.time:
				parser.error("--time is required with --{} '{}'".format(formattpl[1], timelevelname))
		elif args.time:
			logger().warn("--time is useless with --{0} '{1}'; it is only used with --statusof '{2}' or --uninstall '{2}'".format(
				formattpl[1],
				ID_LEVELS[formattpl[0]][0],
				timelevelname
			))
	elif args.install:
		if not args.time:
			parser.error("--time is required with --install")
	elif args.time:
		parser.error("--time can only be combined with --install or --uninstall '{}' actions".format(timelevelname))

	# Sourcefile and destdir are required unless --statusof|uninstall 'all':
	if not ( args.sourcefile and args.destinationdirectory ):
		formattpl = (args.uninstall, "uninstall")
		if args.statusof:
			formattpl = (args.statusof, "statusof")
		if formattpl[0] is not identity_level('all'):
			parser.error("--sourcefile and --destinationdirectory are required with --{} '{}'".format(formattpl[1], formattpl[0]))

	if args.run:
		if args.uninstall:
			parser.error("--run cannot be combined with --uninstall; it can be used on its own or combined with --install.")
		elif args.statusof:
			parser.error("--run cannot be combined with --statusof; it can be used on its own or combined with --install.")

	if not ( args.run or args.install or args.uninstall or args.statusof ):
		parser.error("At least one of --[run,install,uninstall,statusof] is required")

	if args.debug:
		logger().setLevel(logging.DEBUG)
		logger().debug(args)
	return args

# Using the below template so it could easily be put onto the filesystem and
# interpolated with "envsubst" or similar:
def logrotate_template():
	return """
# Environment variables will be interpolated in the below code. Their names and
# values (if they have already been interpolated) are:
# LOGROTATE_SOURCE_FILE:
#	Value (if interpolated): $LOGROTATE_SOURCE_FILE
#	Usage: the path to the file to be backed up.
# LOGROTATE_KEEP_REVISIONS:
#	Value (if interpolated): $LOGROTATE_KEEP_REVISIONS
#	Usage: how many old backed-up revisions to keep
# LOGROTATE_DESTINATION_FOLDER:
#	Value (if interpolated): $LOGROTATE_DESTINATION_FOLDER
#	Usage: folder in which to store backups. Must exist.

$LOGROTATE_SOURCE_FILE {
	# Use date in filename, and stamp it with the second that the file was
	# backed up (in case you want to make more than one backup per day).
	dateext
	dateformat -%Y-%m-%d-%s

	# Leave the old file untouched, and make a copy before backing it up.
	copy
	nocreate

	# Store backups compressed (adds time to backup process; delete or comment
	# the below line if things take too long).
	compress

	# Store backups and stuff in this folder:
	olddir $LOGROTATE_DESTINATION_FOLDER

	# keep this many old backups
	rotate $LOGROTATE_KEEP_REVISIONS

	# Ignore if files are missing
	missingok

	# Don't make backups if file is 0-length
	notifempty

	# Back up files even if they're tiny
	size 0
}
"""

# Build a string of several hashes, adding more info to the hash and catting it
# onto the string at each "identity level". Hashes of the queue name, source and
# destination paths, and scheduling time-string are applied. These are used to
# identify already-scheduled instances of this script, under the assumption that
# it is a lot less likely to falsely match some random other scheduled script if
# it contains the *hash* of the source/dest file paths than if it just contains
# the paths themselves. Absolute paths are used so that different schedulings of
# this script, from different directories, using the same relative path strings
# for source and destination, are not identified as the same.
def get_identifier(args, level=len(ID_LEVELS)):
	idbuilder = hashlib.md5(QUEUE.encode())
	identifier = idbuilder.hexdigest()

	if level > 1:
		idbuilder.update(args.sourcefile.encode())
		idbuilder.update(args.destinationdirectory.encode())
		identifier += "_" + idbuilder.hexdigest()
	if level > 2:
		idbuilder.update(args.time["original"].encode())
		identifier += "_" + idbuilder.hexdigest()

	return identifier

def main():
	args = parse_args()
	exitcode = 0
	if args.install:
		# Thanks to 'at's shell magic, this will propagate between invocations
		# once set.

		relayargs = [ quote(x) for x in (
			sys.executable,
			"-",
			"--sourcefile",
			args.sourcefile,
			"--destdir",
			args.destinationdirectory,
			"--keeprevisions",
			args.keeprevisions,
			"--identifier",
			get_identifier(args),
			"--run",
			"--install",
			"--time",
			args.time["original"]
		)]
		if args.debug:
			relayargs.extend(["--debug", ">>", "debug.txt", "2>&1"])

		# Once a backup job is installed, we want it to run even if the original
		# .py script is [re]moved. In order to accomplish *that*, we need to
		# get the body of the script stored somewhere. Rather than picking another
		# location (e.g. a tempfile) that might get nuked between jobs, we can
		# store it in "at"'s job queue itself, since "at" is nice enough to store
		# a shell script (and propagate environment) for each job, we can take
		# advantage of that for storage. However, that's trickier than it sounds...
		# 
		# This is pretty heinous, but it's the only thing I've found that works:
		# 1. Store the contents of the script into an environment variable if it's
		# not already set. Since we're re-running the script via STDIN, we can't
		# just call inspect's functions each time we run it; since STDIN is a
		# stream, there will be nothing *to* expect. The variable is stored in a
		# here-doc with quotes, to prevent the few '$' signs inside it from being
		# messed with by the shell.
		# 2. When storing thecontents, don't let "at" propagate the variable
		# across multiple runs of the script; instead, export it ourselves and
		# make sure it doesn't get picked up by "at" (in add_atjob()). This is
		# because at (or sh)'s shell escaping for the body of the script if it's
		# just stored in an environment variable is insufficient/broken, and
		# causes a syntax error. The use of "cat" here is *not* useless; since
		# the shell read() *requires* a delimiter, the variable can't be stored
		# by read() alone without getting altered (parts of the backslashes in
		# some of the regexes get eaten). There might be a way around this using
		# read() alone, but "cat" doesn't have the issue at all.
		# 3. Supply the script contents back to Python via *another* here-doc.
		# This is because the raw-heredoc interpolation doesn't remove quotes
		# etc., whereas doing "echo $ATJOB_TINYBACKUP_SCRIPT | python..." does.
		if not "ATJOB_TINYBACKUP_SCRIPT" in os.environ:
			os.environ["ATJOB_TINYBACKUP_SCRIPT"] = inspect.getsource(sys.modules[__name__])
		cmd = "export ATJOB_TINYBACKUP_SCRIPT=$(cat <<'SCRIPT'\n{}\nSCRIPT)\n{} <<COMMAND\n$ATJOB_TINYBACKUP_SCRIPT\nCOMMAND".format(
			os.environ["ATJOB_TINYBACKUP_SCRIPT"],
			" ".join(relayargs),
		)

		logger().debug("Scheduling command: " + cmd)
		add_atjob(cmd, args.time["original"], debug=args.debug)
		i("Scheduled backup to run and re-schedule itself at '{}'".format(args.time["parsed"]))
	elif args.uninstall:
		jobs = get_atjobs_with_string(get_identifier(args, args.uninstall))
		for job in jobs:
			remove_atjob(job["id"])
			i("Removed job ID {id} (scheduled for {schedule})".format(**job))
		if not jobs:
			exitcode = 1
			i("No jobs to remove.\n")
			i("Use {} to remove all backup jobs from queue '{}'".format("--uninstall '{}'".format(ID_LEVELS[identity_level("all")][0]), QUEUE))
			i("Use 'at -l -q {0} | cut -f1 | xargs at -r' to remove all jobs from queue '{0}'".format(QUEUE))
			i("Use 'at -l | cut -f1 | xargs at -r' to remove all scheduled jobs of any kind from this system")
	elif args.statusof:
		identifier = get_identifier(args, args.statusof)
		stripregex = re.compile(r"\s+(?:--identifier\s+\S*{}\S*)\s+".format(re.escape(identifier)))
		jobs = get_atjobs_with_string(identifier)
		if jobs:
			i("Found {} jobs (job IDs are random):\n".format(len(jobs)))
			i("\n\n".join(
				"Job ID {id} is scheduled for {schedule}\nJob command: ".format(**job) + re.sub(stripregex, " ", job["command"])
				for job in jobs
			))
		else:
			exitcode = 1
			i("No jobs found. Do --statusof '{}' to view all jobs in the queue".format(ID_LEVELS[identity_level("all")][0]))

	if args.run:
		# Handles automatic deletion of logrotate state file (our at-stored
		# "state" is canonical; letting logrotate track state as well both
		# creates unexpected messes, and may create unexpected issues), and
		# the logrotate config file.
		with tempfile.NamedTemporaryFile() as f, tempfile.NamedTemporaryFile() as statefile:
			os.environ["LOGROTATE_SOURCE_FILE"] = os.path.realpath(args.sourcefile)
			os.environ["LOGROTATE_KEEP_REVISIONS"] = args.keeprevisions
			os.environ["LOGROTATE_DESTINATION_FOLDER"] = os.path.realpath(args.destinationdirectory)
			logrotateconf = os.path.expandvars(logrotate_template())
			logger().debug("logrotate config about to be installed to '{}':".format(f.name))
			logger().debug("logrotate config contents:\n" + logrotateconf)
			f.write(logrotateconf.encode())
			f.flush()
			logrotateflags = "-v"
			if args.noop:
				logrotateflags += "d"
			subprocess.check_call([
				"logrotate",
				logrotateflags,
				"--state",
				statefile.name,
				f.name
			])


if __name__ == '__main__':
	main()


