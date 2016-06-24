#!/usr/bin/perl

use warnings;
use strict;
use Getopt::Long;
#use Switch;

# globals
my $version = "0.3";

# default command is to run actual load test
my $command = "run";
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
my $noLogCleanup = 0;
#my $eraseLogsOnly = 0;
#my $shutdownOnly = 0;
my $restcommEnableRecording = 0;

# prints out a short usage for the tool
sub printUsage
{
	print "load-runner.pl, Ver. $version\n";
	print "Usage: \$ load-runner.pl <command> [options]\n";
	print "Examples:\n";
	print "\t\$ load-runner.pl --command run --client-count 30 --sipp-total-calls 35000 --sipp-concurrent-calls 10 --sipp-calls-per-second 1 --client-prefix 0user --restcomm-ip 10.142.205.168 --restcomm-account-sid ACae6e420f425248d6a26948c17a9e2acf --restcomm-auth-token 3349145c827863209020dbc513c87260 --restcomm-phone-number \"+5556\"\n";
	print "\t\$ load-runner.pl --command erase-logs\n";
	print "\t\$ load-runner.pl --command shutdown\n";
	print "\t\$ load-runner.pl --command collect-logs\n";
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
		my $currentCount = qx(cd tools; cat *.log* | grep "\] Device is ready" | wc -l);
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


my $result = GetOptions("command|c=s" => \$command,
			"client-count=s" => \$clientCount,
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
			"no-log-cleanup" => \$noLogCleanup,
			#"erase-logs-only" => \$eraseLogsOnly,
			#"shutdown-only" => \$shutdownOnly,
			"help|h" => sub { printUsage(); exit 1; });

if (!$result) {
	print STDERR "[nreg] Error parsing command-line options\n";
	exit 1;
}

if ($command eq "run") {
	# stop any prior instances of load runner
	killProcesses();

	if (!$noLogCleanup) {
		cleanupFiles();
	}

	startXvfb();

	startWebrtcTest();

	if (waitForClients() != 0) {
		print "[load-runner] Clients still unregistered; bailing out\n";
		exit 1;
	}

	startTraffic();
}
elsif ($command eq "erase-logs") {
	cleanupFiles();
	exit 0;
}
elsif ($command eq "shutdown") {
	killProcesses();
	exit 0;
}
elsif ($command eq "collect-logs") {
	my $logFiles = qx(find . -name "*log" -o -name "*log.*");
	chomp($logFiles);
	$logFiles =~ s/\n/ /;

	my $date = qx(date);
	chomp($date);
	# replace spaces in date
	$date =~ s/ /-/g;
	# remove colons that cause issues in the invocation
	$date =~ s/\://g;

	qx(mkdir $date);
	
	qx(cp $logFiles $date/);

	print "Compressing logs into $date.tar.gz\n";
	qx(tar -zcvf $date.tar.gz $date);
	if ($? == 0) {
		qx(rm -fr $date);
	}
	else {
		print "[load-runner] Failed to compress logs";
	}
}

