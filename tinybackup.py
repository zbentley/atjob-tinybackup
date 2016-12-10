#!/usr/bin/env python

import argparse
import os
import subprocess
import re
import hashlib
import tempfile

QUEUE = 'z'
ID_LEVELS = [
	[],
	["all backup jobs", "all"],
	["jobs with this source and destination", "files"],
	["jobs exactly like this one", "this", "thisjob", "time", "bytime"]
]
ARGUMENT_PARSER = argparse.ArgumentParser(description='Schedule a repeated backup of a single file.')

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
		return value
	else:
		ARGUMENT_PARSER.error("'{}' is not a readable file".format(value))

def writable_dir(value):
	if os.path.isdir(value) and os.access(value, os.W_OK):
		return value
	else:
		ARGUMENT_PARSER.error("'{}' is not a writable directory".format(value))

def uninstall_level(value):
	for idx, level in enumerate(ID_LEVELS):
		if value in level:
			return idx
	uninstinfo = "Invalid value for --uninstall. Valid values and their roles are:\n"
	for level in ID_LEVELS:
		uninstinfo += "\tUninstall {}: {}\n".format(level[0], ', '.join('"{0}"'.format(w) for w in level))
	ARGUMENT_PARSER.error(uninstinfo)


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
			job = line.split()[0]
			for statement in reversed(subprocess.check_output(["at", "-c", job]).decode('ascii').split("\n")):
				if statement.strip():
					if string in statement:
						jobs.append(job)
					break
	return jobs

def add_atjob(cmd, timespec):
	cmd = " ".join(cmd)
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
		print("Could not invoke '{}'; this script cannot function".format(cmd[0]))
		raise

def parse_args():
	# We use -l since --help is noncompliant and returns 1
	verify_exe(["at", "-l"])
	verify_exe(["logrotate", "--help"])
	operations = ARGUMENT_PARSER.add_mutually_exclusive_group(required=True)
	operations.add_argument('--run', action='store_true', help='Run a backup immediately.')
	operations.add_argument('--install', action='store_true', help='Schedule this script to run repeatedly at a given time.')
	operations.add_argument('--uninstall', metavar="UNINSTALL_FILTER", type=uninstall_level, help='Remove all scheduled runs of this script for a given SOURCEFILE and DESTINATIONFILE')
	ARGUMENT_PARSER.add_argument('--time', type=valid_atjob_timespec, help="Time in the future to schedule (or uninstall) backup jobs")
	ARGUMENT_PARSER.add_argument('--keeprevisions', metavar='REVISIONS', type=positive_int, default=14, help='How many backups of the file to keep. Old ones will be rotated out.')
	ARGUMENT_PARSER.add_argument('--sourcefile', type=readable_file, metavar='FILE_PATH', help='File to back up.', required=True)
	ARGUMENT_PARSER.add_argument('-d', '--destinationdir', '--destdir', type=writable_dir, metavar='DIRECTORY_PATH', help='Directory in which to store backed up files.', required=True)
	ARGUMENT_PARSER.add_argument('--debug', action='store_true',  help='Enable debug output.')
	ARGUMENT_PARSER.add_argument('--identifier', help=argparse.SUPPRESS)

	args = ARGUMENT_PARSER.parse_args()
	# Check if it was passed a timestamp

	# Do some more complex argument validation: --time is required with --install,
	# and also with --uninstall "jobs exactly like this one". Elsewhere it is
	# meaningless.
	timelevelname = ID_LEVELS[uninstall_level("time")][0]
	if args.uninstall:
		if args.uninstall is uninstall_level("time"):
			ARGUMENT_PARSER.error("--time is required with --uninstall '{}'".format(timelevelname))
		else:
			ARGUMENT_PARSER.error("--time is useless with --uninstall '{}'; it is only used with --uninstall '{}'".format(
				ID_LEVELS[uninstall_level(args.uninstall)][0],
				timelevelname
			))
	elif args.install and not args.time:
		ARGUMENT_PARSER.error("--time is required with --install")
	elif args.time:
		parser.error("--time can only be combined with --install or --uninstall '{}' actions".format(timelevelname))

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
def get_identifiers(args, level=len(ID_LEVELS)):
	idbuilder = hashlib.md5(QUEUE.encode())
	identifier = idbuilder.hexdigest()

	if level > 1:
		idbuilder.update(os.path.abspath(args.sourcefile).encode())
		idbuilder.update(os.path.abspath(args.destinationdir).encode())
		identifier += "_" + idbuilder.hexdigest()
	if level > 2:
		idbuilder.update(args.time["original"].encode())		
		identifier += "_" + idbuilder.hexdigest()

	return identifier

def main():
	args = parse_args()

	if args.install:
		relayargs = [
			__file__,
			"--sourcefile",
			args.sourcefile,
			"--destdir",
			args.destinationdir,
			"--keeprevisions",
			args.keeprevisions,
			"--identifier",
			get_identifiers(args)
		]
		add_atjob(relayargs + ["--run"], args.time["original"])
		print("Scheduled backup to run at '{}'".format(args.time["parsed"]))
		add_atjob(relayargs + ["--install", args.time["original"]], args.time["original"])
		print("Scheduled this job to re-schedule itself at '{}'".format(args.time["parsed"]))
	elif args.uninstall:
		jobs = get_atjobs_with_string(get_identifiers(args, args.uninstall))
		for job in jobs:
			remove_atjob(job)
			print("Removed job '{}'".format(job))
		if not jobs:
			print("No jobs to remove.\n")
			print("Use '{} {}' to remove all backup jobs from queue '{}'".format(__file__, '--uninstall "all backup jobs"', QUEUE))
			print("Use 'at -l -q {0} | cut -f1 | xargs at -r' to remove all jobs from queue '{0}'".format(QUEUE))
			print("Use 'at -l | cut -f1 | xargs at -r' to remove all scheduled jobs of any kind from this system")

	else: # args.run
		destdir = os.path.abspath(args.destinationdir)
		statefile = os.path.join(destdir, "logrotate.state")
		with tempfile.NamedTemporaryFile() as f:
			os.environ["LOGROTATE_SOURCE_FILE"] = os.path.abspath(args.sourcefile)
			os.environ["LOGROTATE_KEEP_REVISIONS"] = args.keeprevisions
			os.environ["LOGROTATE_DESTINATION_FOLDER"] = destdir
			logrotateconf = os.path.expandvars(logrotate_template())
			if args.debug:
				print("Logrotate config about to be installed to '{}':".format(f.name))
				print(logrotateconf)
			f.write(logrotateconf.encode())
			f.flush()

			with tempfile.NamedTemporaryFile() as statefile:
				logrotateflags = "-v"
				if args.debug:
					logrotateflags += "d"
				subprocess.check_call([
					"logrotate",
					logrotateflags,
					"--state",
					statefile.name,
					f.name
				])
main()