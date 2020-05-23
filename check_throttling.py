while true; do vcgencmd measure_temp && vcgencmd measure_clock arm && vcgencmd get_throttled; sleep 2; echo ''; done
