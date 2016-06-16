#!/usr/bin/perl

use warnings;
use strict;
use Getopt::Long;

# globals
my $version = "0.3";

my $clientCount = "30";
my $clientPrefix = "user";
my $clientPassword = "1234";
my $clientBrowser = "chromium-browser";
# grab eth0 interface ip address
my $headlessIp = qx(ifconfig eth0 | perl -n -e 'if (m/inet addr:([\\d\\.]+)/g) { print \$1 }');
my $restcommIp = "10.142.205.168";
my $restcommAccountSid = "ACae6e420f425248d6a26948c17a9e2acf";
my $restcommAuthToken = "3349145c827863209020dbc513c87260";
my $restcommPhoneNumber = "+5556";
my $webrtcTestOutputFile = "webrtc-test-run.log";
my $sippOutputFile = "sipp-run.log";
my $sippConcurrentCalls = "10";
my $sippTotalCalls = "10000";
my $sippCallsPerSecond = "1";
my $cleanupBeforeRun = 1;
my $eraseLogsOnly = 0;
my $shutdownOnly = 0;
my $restcommEnableRecording = 0;

# prints out a short usage for the tool
sub printUsage
{
	print "load-runner.pl, Ver. $version\n";
	#print "Usage: \$ load-runner.pl [ -s ] [-f <import file>] [-l <import log master>] [-x <export master>]\n";
	#print "Examples:\n";
	#print "\t\$ nreg.pl -t testcases.txt                                                - run all tests included in the test case file (full regression run)\n";
	#print "\t\$ nreg.pl -f import.txt -l log-master.txt -x export-master.txt            - run a single import/export test\n";
	#print "\t\$ nreg.pl -g file -f import.txt -l log-master.txt -x export-master.txt    - generate log master and export master from the given import file\n";
}

# kill all load test processes
sub killProcesses
{
	print "[load-runner] Killing load test processes\n";
	qx(sudo pkill sipp; sudo pkill python; sudo pkill node; sudo pkill chrom);
}

# cleanup log files, etc from previous runs
sub cleanupFiles
{
	print "[load-runner] Cleaning up log files\n";
	qx(rm -fr tools/*log.* tools/*log webrtc-load-tests/*log);
}

# start Xvfb if not already running
sub startXvfb
{
	my $stdout = qx(ps -ef | grep Xvfb | grep -v grep | wc -l);
	if (int($stdout) == 0) {
		print "[load-runner] Starting Xvfb\n";
		qx(Xvfb :99 &);
	}
	else {
		print "[load-runner] Xvfb already running\n";
	}
}


# start webrtc-test.py
sub startWebrtcTest
{
	my $enableRecordingOption = "";
	if ($restcommEnableRecording) {
		$enableRecordingOption = "--restcomm-record-media";
	}
	my $cmd = "cd tools; nohup ./webrtc-test.py --client-count " . $clientCount . " --client-url https://" . $headlessIp . ":10510/webrtc-client.html --client-register-ws-url wss://" . $restcommIp . ":5083 --client-register-domain " . $restcommIp . " --client-username-prefix " . $clientPrefix . " --client-password " . $clientPassword . " --restcomm-account-sid " . $restcommAccountSid . " --restcomm-auth-token " . $restcommAuthToken . " --restcomm-base-url https://" . $restcommIp . ":8443 --restcomm-phone-number \"" . $restcommPhoneNumber . "\" --restcomm-external-service-url http://" . $headlessIp . ":10512/rcml --client-browser \"" . $clientBrowser . "\" --client-web-app-dir ../webrtc-load-tests/ --client-headless --client-headless-x-display \":99\" --client-respawn --client-respawn-url https://" . $headlessIp . ":10511/respawn-user " . $enableRecordingOption . " < /dev/null > " . $webrtcTestOutputFile . " 2>&1 &";
	print "[load-runner] Starting webrtc-test.py, \$ " . $cmd . "\n";

	qx($cmd);
}

# wait for webrtc clients to register
sub waitForClients
{
	my $counter = 0;
	while ($counter < 30) {
		my $currentCount = qx(cd tools; cat *.log* | grep "WebRTCommClient:open" | wc -l);
		chomp($currentCount);
		if ($currentCount eq $clientCount) {
			print "[load-runner] All clients are registered: " . $currentCount . "/" . $clientCount . "\n";
			return 0;
		}
		else {
			print "[load-runner] Still waiting for clients to register: " . $currentCount . "/" . $clientCount . "\n";
		}
		sleep 1;
		$counter += 1;
	}

	# error some/all clients still unregistered
	return 1;
}

# start sipp traffic
sub startTraffic
{
	my $cmd = "cd webrtc-load-tests; nohup sudo sipp -sf webrtc-sipp-client.xml -s " . $restcommPhoneNumber . " " . $restcommIp . ":5080 -mi " . $headlessIp . ":5090 -l " . $sippConcurrentCalls . " -m " . $sippTotalCalls . " -r " . $sippCallsPerSecond . " -trace_screen -trace_err -recv_timeout 5000 -nr -t u1  < /dev/null > " . $sippOutputFile . " 2>&1 &";
	print "[load-runner] Starting sipp traffic, \$ " . $cmd . "\n";

	qx($cmd);
}

#------------------------------# MAIN CODE #------------------------------#

my $num_args = $#ARGV + 1;
if ($num_args < 0) {
	print "args: " . $num_args . "\n";
	printUsage();
	exit 1;
}


my $result = GetOptions("client-count|c=s" => \$clientCount,
			"client-prefix=s" => \$clientPrefix,
			"client-password=s" => \$clientPassword,
			"client-browser=s"	=> \$clientBrowser,
			"headless-ip=s"	=> \$headlessIp,
			"restcomm-ip=s" => \$restcommIp,
			"restcomm-account-sid=s" => \$restcommAccountSid,
			"restcomm-auth-token=s" => \$restcommAuthToken,
			"restcomm-phone-number=s" => \$restcommPhoneNumber,
			"restcomm-enable-recording=i" => \$restcommEnableRecording,
			"sipp-concurrent-calls=s" => \$sippConcurrentCalls,
			"sipp-total-calls=s" => \$sippTotalCalls,
			"sipp-calls-per-second=s" => \$sippCallsPerSecond,
			"cleanup-before-run=i" => \$cleanupBeforeRun,
			"erase-logs-only=i" => \$eraseLogsOnly,
			"shutdown-only=i" => \$shutdownOnly,
			"help|h" => sub { printUsage(); exit 1; });

if (!$result) {
	print STDERR "[nreg] Error parsing command-line options\n";
	exit 1;
}

if ($eraseLogsOnly) {
	cleanupFiles();
	exit 0;
}

if ($shutdownOnly) {
	killProcesses();
	exit 0;
}

if ($cleanupBeforeRun) {
	killProcesses();
	cleanupFiles();
}

startXvfb();

startWebrtcTest();

if (waitForClients() != 0) {
	print "[load-runner] Clients still unregistered; bailing out\n";
	exit 1;
}

startTraffic();

