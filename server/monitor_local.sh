while : ; do
wget -q -O /dev/null -T 5 http://bestminer.io/auth/login
ret=$?
if [ "$ret" -ne "0" ] ; then
	echo "error ($ret)"
	date
	./gunicorn1.sh restart
fi
sleep 60
done >> ./monitor.log
