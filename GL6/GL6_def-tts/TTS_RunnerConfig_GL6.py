# Some of this code has been adjusted from a previous version developed by Madalina Dinga
import os
import subprocess
import paramiko
import time
import datetime

from EventManager.Models.RunnerEvents import RunnerEvents
from EventManager.EventSubscriptionController import EventSubscriptionController
from ConfigValidator.Config.Models.RunTableModel import RunTableModel
from ConfigValidator.Config.Models.FactorModel import FactorModel
from ConfigValidator.Config.Models.RunnerContext import RunnerContext
from ConfigValidator.Config.Models.OperationType import OperationType
from ExtendedTyping.Typing import SupportsStr
from ProgressManager.Output.OutputProcedure import OutputProcedure as output
from ConnectionHandler import ConnectionHandler

from typing import Dict, List, Any, Optional
from pathlib import Path
from os.path import dirname, realpath

# LOCAL SCOPE
def get_Rittal_credentials():
    username = os.getenv("RITTAL_U_3")
    password = os.getenv("RITTAL_P_3")
    if not password or not username:
        raise Exception('No environment variables set for credentials')
    return username, password  

# Open a terminal and execute a command in the local machine
def execute_local_command(command, wait, mssg=""):
    process = subprocess.Popen(command, shell=True, executable='/bin/bash')
    output.console_log(f'Running {command}')
    if wait: 
        process.communicate()        
    return process

def write_to_log(mssg, sut, add_timestamp=False):
    with open(f'logfile{sut}.log', 'a') as file:
        if add_timestamp:
            timestamp = datetime.datetime.now()
            file.write(f"{mssg} at {timestamp}\n")
        else:
            file.write(f"{mssg}\n")

class RunnerConfig:
    ROOT_DIR = Path(dirname(realpath(__file__)))

    # ================================ USER SPECIFIC CONFIG ================================
    """The name of the experiment."""
    name:                       str             = "def-tts-GL6"

    """The path in which Experiment Runner will create a folder with the name `self.name`, in order to store the
    results from this experiment. (Path does not need to exist - it will be created if necessary.)
    Output path defaults to the config file's path, inside the folder 'experiments'"""
    results_output_path:        Path            = ROOT_DIR / 'experiments'

    """Experiment operation type. Unless you manually want to initiate each run, use `OperationType.AUTO`."""
    operation_type:             OperationType   = OperationType.AUTO

    """The time Experiment Runner will wait after a run completes.
    This can be essential to accommodate for cooldown periods on some systems."""
    time_between_runs_in_ms:    int             = 1000 * 60 * 5 # 5 minutes sleep between runs
   
    # USER VARIABLES:
    # Path for local scripts
    scripts_path:               Path            = "~/THESIS/master-project-def/scripts"
    # System Under Test (SUT)
    SUT:                        str             = "GL6"
    # Logging server
    LOGGING_GL:                 str             = "GL3"
    # Connections with GLs
    con_SUT:                    ConnectionHandler = ConnectionHandler(SUT)
    con_LOG:                    ConnectionHandler = ConnectionHandler(LOGGING_GL)
    # Discard run
    discard_run:                bool            = False
    # GL specific
    VUs_dict:                   Dict            = {'50': '500', '75': '750', '100': '1500' }
    wait_time:                  int             = 3 * 60
    local_stressing:            bool            = False
    # Testing mode
    testing:                    bool            = False

    # Dynamic configurations can be one-time satisfied here before the program takes the config as-is
    # e.g. Setting some variable based on some criteria
    def __init__(self):
        """Executes immediately after program start, on config load"""
        EventSubscriptionController.subscribe_to_multiple_events([
            (RunnerEvents.BEFORE_EXPERIMENT, self.before_experiment),
            (RunnerEvents.BEFORE_RUN       , self.before_run       ),
            (RunnerEvents.START_RUN        , self.start_run        ),
            (RunnerEvents.START_MEASUREMENT, self.start_measurement),
            (RunnerEvents.INTERACT         , self.interact         ),
            (RunnerEvents.STOP_MEASUREMENT , self.stop_measurement ),
            (RunnerEvents.STOP_RUN         , self.stop_run         ),
            (RunnerEvents.POPULATE_RUN_DATA, self.populate_run_data),
            (RunnerEvents.AFTER_EXPERIMENT , self.after_experiment )
        ])
        self.run_table_model = None  # Initialized later

        output.console_log("Custom config loaded")

    def create_run_table_model(self) -> RunTableModel:
        """Create and return the run_table model here. A run_table is a List (rows) of tuples (columns),
        representing each run performed"""
        factor1 = FactorModel("runs", ['r1', 'r2', 'r3', 'r4', 'r5', 'r6', 'r7', 'r8', 'r9', 'r10'])
        #factor1 = FactorModel("runs", ['r1', 'r2'])
        factor2 = FactorModel("workload", ['50', '75', '100'])
        self.run_table_model = RunTableModel(
            factors=[factor1, factor2],
            data_columns=['avg_cpu', 'avg_mem']
        )
        return self.run_table_model

    def interrupt_run(self, context, msg):
        self.stop_measurement(context)
        self.stop_run(context)
        output.console_log_FAIL(msg)
        raise Exception(msg)

    def before_experiment(self) -> None:
        """Perform any activity required before starting the experiment here
        Invoked only once during the lifetime of the program."""
        output.console_log("Config.before_experiment() called!")
        ################################################## BEFORE_EXPERIMENT
        os.environ.update() # For the environment variables to be loaded
        execute_local_command(f"cd {self.ROOT_DIR} && mkdir -p results/energy", True)
        # Improve K6's performance 
        # on LOCAL machine
        if self.local_stressing:
            local_pass = os.getenv("PASS_U")
            execute_local_command(f"echo {local_pass} | sudo -S sysctl -w net.ipv4.ip_local_port_range=\"1024 65535\"", True)
            execute_local_command(f"echo {local_pass} | sudo -S sysctl -w net.ipv4.tcp_tw_reuse=1", True)
            execute_local_command(f"echo {local_pass} | sudo -S sysctl -w net.ipv4.tcp_timestamps=1", True)
            execute_local_command("ulimit -n 250000", True)
        # on other SUT
        else:
            con_other_SUT = ConnectionHandler("GL5")
            _, _, passOther = con_other_SUT.get_credentials()
            con_other_SUT.execute_remote_command(f"echo {passOther} | sudo -S sysctl -w net.ipv4.ip_local_port_range=\"1024 65535\"", "Upgrades1")
            con_other_SUT.execute_remote_command(f"echo {passOther} | sudo -S sysctl -w net.ipv4.tcp_tw_reuse=1", "Upgrades2")
            con_other_SUT.execute_remote_command(f"echo {passOther} | sudo -S sysctl -w net.ipv4.tcp_timestamps=1", "Upgrades3")
            con_other_SUT.execute_remote_command("ulimit -n 250000", "Upgrades4")


        write_to_log(f"[{self.name}] New experiment started from scratch", self.SUT, True)

    def before_run(self) -> None:
        """Perform any activity required before starting a run.
        No context is available here as the run is not yet active."""
        output.console_log("Config.before_run() called!")
        ################################################## BEFORE_RUN
        self.discard_run = False
        self.con_SUT.execute_remote_command("tmux kill-server", "Kill tmux sessions in case there were any left (SUT).")
        self.con_LOG.execute_remote_command("tmux kill-server", "Kill tmux sessions in case there were any left (LOG).")
        execute_local_command("tmux kill-server", "Kill tmux sessions (local).")

    def start_run(self, context: RunnerContext) -> None:
        """Perform any activity required for starting the run here.
        Activities after starting the run should also be performed here."""
        output.console_log("Config.start_run() called!")
        ################################################## START_RUN

        workload = context.run_variation['workload']
        # SSH port forwarding for Rittal system
        hostLog, usernameLog, passwordLog = self.con_LOG.get_credentials()
        ssh_port_forwarding_command = f"tmux new -s portforwarding -d \"sshpass -p {passwordLog} ssh -L 8080:192.168.0.200:80 {usernameLog}@{hostLog}\""
        execute_local_command(ssh_port_forwarding_command, False)

        time.sleep(3)
        
        # connect to SUT
        _, _, passSUT = self.con_SUT.get_credentials()

        # launch TTS
        tts_deployment_start = f"tmux new -s tts -d 'cd ~/tts-thesis; echo {passSUT} | sudo -S docker compose -f docker-compose-{self.SUT}-{workload}.yml up -d'"
        if(self.con_SUT.execute_remote_command(tts_deployment_start, f"Running TTS with CPU% of {workload}") == 0):
            self.interrupt_run(context, "Encountered an error while starting system")

        output.console_log("Waiting for Train Ticket System to start up")

        output.console_log(f"Sleep {self.wait_time/60} minutes...")

        time.sleep(self.wait_time)

        num_containers = self.con_SUT.get_containers_count()

        # check number of containers to be sure the TTS is properly working
        if num_containers < 68:
            output.console_log(f"Sleep for {self.wait_time/60} more minutes...")
            time.sleep(self.wait_time)

            num_containers = self.con_SUT.get_containers_count()

            if num_containers < 68:
                error_msg = f"Not enough containers running: {num_containers}/68"
                # log if not working
                write_to_log(f"[{context.run_variation['runs']}] [{workload}] Not enough containers. FAILED", self.SUT, True)
                if not self.testing:
                    self.discard_run = True
                    self.con_SUT.execute_remote_command(f"echo {passSUT} | sudo -S reboot", "REBOOT SUT")
                time.sleep(self.wait_time*2)                
                # cleanup if not running
                self.interrupt_run(context, error_msg)

        output.console_log("Benchmark system initialized and running")

    def start_measurement(self, context: RunnerContext) -> None:
        """Perform any activity required for starting measurements."""
        output.console_log("Config.start_measurement() called!")
        ################################################## START_MEASUREMENT
        # start Rittal system on LOGGING_SERVER for 15' = 900s (average run is 16')
        timeout = 900
        userRittal, passwordRittal = get_Rittal_credentials()
        rittal_command = f"{self.scripts_path}/experiment-runner/logging/start_Rittal.sh {self.SUT} {timeout} {self.ROOT_DIR}/results/energy {userRittal} {passwordRittal}"
        execute_local_command(rittal_command, False)
        time.sleep(12)
        workload = context.run_variation['workload']
        # check whether Rittal worked:
        file_path = os.path.join(f"{self.ROOT_DIR}/results/energy/", f"energy{self.SUT}.log")
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        if not os.path.exists(file_path):
            error_msg = "Rittal could not start successfully. Stopping the run."
            # log if not working
            write_to_log(f"[{context.run_variation['runs']}] [{context.run_variation['workload']}] RITTAL FAILED", self.SUT, True)
            self.discard_run = True
            self.interrupt_run(context, error_msg)
        else:
            # log if working
            write_to_log(f"[{context.run_variation['runs']}-{timestamp}] [{context.run_variation['workload']}] OK", self.SUT, False)

        # start monitor.sh on SUT
        try:
            VUs = self.VUs_dict[workload]
            monitor_start_command = f"tmux new -s monitor -d 'cd /home/ander/scripts && ./monitor-er.sh {self.SUT} {workload} {VUs}'"
        except:
            monitor_start_command = f"tmux new -s monitor -d 'cd /home/ander/scripts && ./monitor-er.sh {self.SUT} {workload}'"
        self.con_SUT.execute_remote_command(monitor_start_command, "Monitor CPU & MEM started")        

    def interact(self, context: RunnerContext) -> None:
        """Perform any interaction with the running target system here, or block here until the target finishes."""
        output.console_log("Config.interact() called!")
        ################################################## INTERACT
        timestamp_ini = time.time()
        workload = context.run_variation['workload']
        output.console_log(f"Load testing with K6 - CPU%:{workload}; VUs: {self.VUs_dict[workload]}") 
        # we prepare the tests with the corresponding IPs
        # LOCAL
        if self.local_stressing:
            os.system(f"for i in $(ls ~/THESIS/k6-tests/k6-test-{self.SUT}); "
                    f"do k6 run - <~/THESIS/k6-tests/k6-test-{self.SUT}/$i/script.js --vus {self.VUs_dict[workload]} --duration 20s ; done") 
        # from other SUT
        else:
            con_other_SUT = ConnectionHandler("GL5")    
            con_other_SUT.execute_remote_command(f"for i in $(ls ~/k6-tests/k6-test-{self.SUT});" 
                f"do k6 run - <~/k6-tests/k6-test-{self.SUT}/$i/script.js --vus {self.VUs_dict[workload]} --duration 20s ;done", "Load testing from GL5")       
        output.console_log('Finished load testing')
        if time.time() - timestamp_ini < 120:
            print(time.time() - timestamp_ini)
            self.discard_run = True

            write_to_log(f"[{context.run_variation['runs']}] [{workload}] FAILED during K6-test", self.SUT, True)

    def stop_measurement(self, context: RunnerContext) -> None:
        """Perform any activity here required for stopping measurements."""
        output.console_log("Config.stop_measurement called!")
        ################################################## STOP_MEASUREMENT
        # stop Rittal if still running, process the .log and generate csv in results if the run is valid
        if self.discard_run:
            self.con_SUT.execute_remote_command("pgrep -f \"start_Rittal.sh\" | xargs kill ; tmux kill-window", "Kill Rittal script and tmux session.")
        else:
            try:
                VUs = self.VUs_dict[context.run_variation['workload']]
                execute_local_command(f"{self.scripts_path}/experiment-runner/logging/stop_Rittal.sh {self.SUT} {self.ROOT_DIR}/results/energy {context.run_variation['workload']} {VUs}", True)
            except:
                output.console_log("VUs not being treated as a factor")
                execute_local_command(f"{self.scripts_path}/experiment-runner/logging/stop_Rittal.sh {self.SUT} {self.ROOT_DIR}/results/energy {context.run_variation['workload']}", True)         
        # stop monitor-er.sh
        self.con_SUT.execute_remote_command("tmux kill-session -t monitor", "Kill tmux monitor session")
        if self.discard_run: 
            # remove mem and cpu files from incompleted run
            self.con_SUT.execute_remote_command("~/scripts/remove_2_last_files.sh ~/results/", "Delete 2 extra files")

    def stop_run(self, context: RunnerContext) -> None:
        """Perform any activity here required for stopping the run.
        Activities after stopping the run should also be performed here."""
        output.console_log("Config.stop_run() called!")
        ################################################## STOP_RUN
        _, _, password = self.con_SUT.get_credentials()
        output.console_log(f"Stopping TTS")
        # Stop the tts system
        self.con_SUT.execute_remote_command("tmux kill-session -t tts", "Kill tmux train session")

        # Build commands       
        # prune --all does not work in GL6/GL2 for some reason
        prune_docker_volumes = f"echo {password} | sudo -S /home/ander/scripts/remove-docker-volumes.sh"
        stop_docker_command = f"echo {password} | sudo -S systemctl stop docker"
        start_docker_command = f"echo {password} | sudo -S systemctl start docker"
        # 1st prune, then restart docker and remove created resources
        self.con_SUT.execute_remote_command(stop_docker_command , "Stop docker system")
        self.con_SUT.execute_remote_command(start_docker_command , "Start docker system")
        # Stop TTS if it starts over
        stop_tts_command = (f"cd ~/tts-thesis; echo {password} | sudo -S docker compose -f docker-compose-{self.SUT}-{context.run_variation['workload']}.yml down")
        self.con_SUT.execute_remote_command(stop_tts_command, "STOP TTS")
        self.con_SUT.execute_remote_command(prune_docker_volumes , "Prune volumes")

    def populate_run_data(self, context: RunnerContext) -> Optional[Dict[str, SupportsStr]]:
        """Parse and process any measurement data here.
        You can also store the raw measurement data under `context.run_dir`
        Returns a dictionary with keys `self.run_table_model.data_columns` and their values populated"""
        output.console_log("Config.populate_run_data() called!")
        ################################################## POPULATE_RUN
        context.run_dir
        
        return None

    def after_experiment(self) -> None:
        """Perform any activity required after stopping the experiment here
        Invoked only once during the lifetime of the program."""
        ################################################## AFTER_EXPERIMENT

        # retrieve output from SUT (generated with monitor-er.sh)
        execute_local_command(f"cd {self.ROOT_DIR} && mkdir -p results/cpu_mem", True)
        hostSUT, userSUT, passwordSUT = self.con_SUT.get_credentials()
        retrieve_data_cpu_command = f'sshpass -p "{passwordSUT}" scp -r {userSUT}@{hostSUT}:/home/ander/results/* {self.ROOT_DIR}/results/cpu_mem/'
        execute_local_command(retrieve_data_cpu_command, True)
        if self.testing:
            command = (f"echo {passwordSUT} | sudo -S rm -r /home/ander/results/*")
            self.con_SUT.execute_remote_command(command, f"Remove files from {self.SUT}")

        output.console_log(f'CPU & mem data successfully retrieved')

        # move to 0_RESULTS
        timestamp = datetime.datetime.now().strftime("%m%d-%H%M")
        execute_local_command(f"{self.scripts_path}/analysis/analyse_files.sh {self.ROOT_DIR}/results", True)
        execute_local_command(f"cd ~/THESIS/0_RESULTS/TTS && mkdir -p {self.SUT}-{timestamp} && cp -r {self.ROOT_DIR}/results/* ~/THESIS/0_RESULTS/TTS/{self.SUT}-{timestamp}", True)        

        write_to_log(f"[{self.name}] Experiment completed", self.SUT, True)

        output.console_log(f'Experiment completed and data pre-analysed, find the results on ~/THESIS/0_RESULTS/{self.SUT}-{timestamp}')

    # ================================ DO NOT ALTER BELOW THIS LINE ================================
    experiment_path:            Path             = None
