#if { $argc != 3 } {
        #puts "Usage: build.tcl proj_path device ip_dir"
		#exit
    #}

set proj_path [lindex $argv 0]
#set device [lindex $argv 1]
#set ip_dir [lindex $argv 2]
file mkdir $proj_path/build
cd $proj_path/build
create_project -part __CAAS_PART -force v_proj
set_property target_language Verilog [current_project]

#read_ip $ip_dir/clk_wiz_0/clk_wiz_0.xci
#upgrade_ip -quiet [get_ips *]
#generate_target {all} [get_ips *]

read_verilog [glob __CAAS_SOURCES]
read_xdc [glob __CAAS_XDC]

#set outputDir .
#file mkdir $outputDir

synth_design -top __CAAS_TOP
opt_design
place_design
phys_opt_design
route_design

write_bitstream -verbose -force __CAAS_TOP.bit
report_utilization -file util.rpt
report_timing_summary -file timing.rpt

