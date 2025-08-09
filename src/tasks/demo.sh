#!/bin/bash

echo "Welcome to SDCI!"
sleep 1

echo "This is a example of script that you can create in order to deploy your project to your project"
sleep 1

echo "Please look for more info on our project page!"
sleep 1

echo "I'm trying to simulate a long script running... The stream will be sent as soon as we receive it!"
sleep 1

echo "Try to pass sequential params and you can check it here: $@"
sleep 1

echo "It gets more useful because this container has support for docker-cli, so you just need to mount your docker sock."
sleep 1

docker ps -a
sleep 1

echo "Easy, doesn't it?"
sleep 1

echo "Error commands will be sent to STDOUT as well"
command_not_exists
sleep 1

echo "Have fun!"
echo 1
