#!/usr/bin/env python

import argparse
import os
import subprocess
import re
import hashlib
import tempfile
import logging
import sys
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

# Global vars

ARGUMENT_PARSER = argparse.ArgumentParser(description='Schedule a repeated backup of a single file.')

def i(msg):
	return logger().info(msg)

def positive_int(value):
	ivalue = 0
	try:
		ivalue = int(value)
	except ValueError:
		pass
	if ivalue <= 0:
		ARGUMENT_PARSER.error("'{}' is an invalid value; must be >= 0".format(value))
	return str(ivalue)

# We won't use argparse's FileTypes, since they allow STDIN to be used, which
# messes up our ability to do fingerprinting.
def readable_file(value):
	if os.path.isfile(value) and os.access(value, os.R_OK):
		return os.path.realpath(value)
	else:
		ARGUMENT_PARSER.error("'{}' is not a readable file".format(value))

def writable_dir(value):
	if os.path.isdir(value) and os.access(value, os.W_OK):
		return os.path.realpath(value)
	else:
		ARGUMENT_PARSER.error("'{}' is not a writable directory".format(value))

def identity_level(value):
	value = value.lower()
	for idx, level in enumerate(ID_LEVELS):
		if value in level:
			return idx
	uninstinfo = "Invalid value '{}' for --uninstall. Valid values and their roles are:\n".format(value)
	for level in ID_LEVELS[1:]:
		uninstinfo += "Uninstall {}: {}\n".format(level[0], ', '.join('"{0}"'.format(w) for w in level))
	ARGUMENT_PARSER.error(uninstinfo.rstrip())


# Validates a timespec with "at". This could technically be done by just calling
# "at" with no STDIN, waiting for a bit, and seeing if it exited with an error
# or just hung waiting for input, but that requires thinking about timeouts, and
# loses us the ability to get the at-formatted timestamp back for examination.
def valid_atjob_timespec(timespec):
	try:
		jobnum, timestring = add_atjob(["/bin/true"], timespec)
	except subprocess.CalledProcessError as e:
		ARGUMENT_PARSER.error(e.output.strip())
	else:
		try:
			remove_atjob(jobnum)
		except subprocess.CalledProcessError as e:
			ARGUMENT_PARSER.error(e.output.strip())
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
			for statement in reversed(subprocess.check_output(["at", "-c", job]).decode('ascii').split("\n")):
				if statement.strip():
					if string in statement:
						job = {
							"id": job,
							"schedule": " ".join(line).strip(),
							"command": statement,
						}
						logger().debug("found job: " + str(job))
						jobs.append(job)
					break
	return jobs

def add_atjob(cmd, timespec):
	cmd = " ".join(quote(x) for x in cmd)
	# cmd += " >> debug.txt 2>&1"
	r, w = os.pipe()
	os.write(w, cmd.encode())
	os.close(w)
	
	output = subprocess.check_output(["at", "-q", QUEUE, timespec], stdin=r, stderr=subprocess.STDOUT).decode('ascii')
	matches = re.search("job (\d+) at(.+)", str(output))
	if not (matches and matches.group(1) and matches.group(2)):
		raise subprocess.CalledProcessError("Couldn't get job info after successful installation of '{}'".format(cmd))
	return (int(matches.group(1).strip()), matches.group(2).strip())

def verify_exe(cmd):
	try:
		# We use -l since --help is noncompliant and returns 1
		subprocess.check_call(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	except:
		i("Could not invoke '{}'; this script cannot function".format(cmd[0]))
		raise

def parse_args():
	# We use -l since --help is noncompliant and returns 1
	verify_exe(["at", "-l"])
	verify_exe(["logrotate", "--help"])
	operations = ARGUMENT_PARSER.add_mutually_exclusive_group(required=True)
	operations.add_argument('-r', '--run', action='store_true', help='Run a backup immediately.')
	operations.add_argument('-i', '--install', action='store_true', help='Schedule this script to run repeatedly at a given time.')
	operations.add_argument('-u', '--uninstall', metavar="UNINSTALL_FILTER", type=identity_level, help='Remove all scheduled runs of this script for a given SOURCEFILE and DESTINATIONFILE')
	operations.add_argument('-a', '--statusof', metavar="STATUS_FILTER", type=identity_level, help='Display all already-scheduled runs of this script for a given SOURCEFILE and DESTINATIONFILE')
	ARGUMENT_PARSER.add_argument('-t', '--time', type=valid_atjob_timespec, help="Time in the future to schedule (or uninstall) backup jobs")
	ARGUMENT_PARSER.add_argument('-k', '--keeprevisions', metavar='REVISIONS', type=positive_int, default=14, help='How many backups of the file to keep. Old ones will be rotated out.')
	ARGUMENT_PARSER.add_argument('-s', '--sourcefile', type=readable_file, metavar='FILE_PATH', help='File to back up.', required=True)
	ARGUMENT_PARSER.add_argument('-d', '--destinationdir', '--destdir', type=writable_dir, metavar='DIRECTORY_PATH', help='Directory in which to store backed up files.', required=True)
	ARGUMENT_PARSER.add_argument('--debug', action='store_true',  help='Enable debug output.')
	ARGUMENT_PARSER.add_argument('--identifier', help=argparse.SUPPRESS)

	args = ARGUMENT_PARSER.parse_args()
	# Check if it was passed a timestamp

	# Do some more complex argument validation: --time is required with --install,
	# and also with --uninstall/status "jobs exactly like this one". Elsewhere it is
	# meaningless.
	timelevelname = ID_LEVELS[identity_level("exact")][0]
	if args.uninstall or args.statusof:
		formattpl = (args.uninstall, "uninstall")
		if args.statusof:
			formattpl = (args.statusof, "statusof")
		if formattpl[0] is identity_level("exact"):
			if not args.time:
				ARGUMENT_PARSER.error("--time is required with --{} '{}'".format(formattpl[1], timelevelname))
		elif args.time:
			logger().warn("--time is useless with --{0} '{1}'; it is only used with --statusof '{2}' or --uninstall '{2}'".format(
				formattpl[1],
				ID_LEVELS[formattpl[0]][0],
				timelevelname
			))
	elif args.install:
		if not args.time:
			ARGUMENT_PARSER.error("--time is required with --install")
	elif args.time:
		ARGUMENT_PARSER.error("--time can only be combined with --install or --uninstall '{}' actions".format(timelevelname))

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
		idbuilder.update(args.sourcefile)
		idbuilder.update(args.destinationdir)
		identifier += "_" + idbuilder.hexdigest()
	if level > 2:
		idbuilder.update(args.time["original"].encode())		
		identifier += "_" + idbuilder.hexdigest()

	return identifier

def main():
	args = parse_args()
	exitcode = 0
	if args.install:
		relayargs = [
			os.path.realpath(__file__),
			"--sourcefile",
			args.sourcefile,
			"--destdir",
			args.destinationdir,
			"--keeprevisions",
			args.keeprevisions,
			"--identifier",
			get_identifier(args)
		]
		add_atjob(relayargs + ["--run"], args.time["original"])
		i("Scheduled backup to run at '{}'".format(args.time["parsed"]))
		add_atjob(relayargs + ["--install", "--time", args.time["original"]], args.time["original"])
		i("Scheduled this job to re-schedule itself at '{}'".format(args.time["parsed"]))
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
	else: # args.run
		# Handles automatic deletion of logrotate state file (our at-stored
		# "state" is canonical; letting logrotate track state as well both
		# creates unexpected messes, and may create unexpected issues), and
		# the logrotate config file.
		with tempfile.NamedTemporaryFile() as f, tempfile.NamedTemporaryFile() as statefile:
			os.environ["LOGROTATE_SOURCE_FILE"] = os.path.realpath(args.sourcefile)
			os.environ["LOGROTATE_KEEP_REVISIONS"] = args.keeprevisions
			os.environ["LOGROTATE_DESTINATION_FOLDER"] = args.destinationdir
			logrotateconf = os.path.expandvars(logrotate_template())
			logger().debug("logrotate config about to be installed to '{}':".format(f.name))
			logger().debug("logrotate config contents:\n" + logrotateconf)
			f.write(logrotateconf.encode())
			f.flush()
			logrotateflags = "-v"
			if args.debug:
				logrotateflags += "d"
			subprocess.check_call([
				"logrotate",
				logrotateflags,
				"--state",
				statefile.name,
				f.name
			], stdout=sys.stdout, stderr=sys.stderr)


if __name__ == '__main__':
	main()