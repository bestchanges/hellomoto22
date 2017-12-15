while : ; do
wget -q -O /dev/null -T 5 http://localhost:5000/auth/login
ret=$?
if [ "$ret" -ne "0" ] ; then
	echo error
	date
	./bestminer-server.sh restart
fi
sleep 60
done >> ./monitor.log
