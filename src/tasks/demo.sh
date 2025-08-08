#!/bin/bash

echo "Welcome to SDCI!"
sleep 3

echo "This is a example of script that you can create in order to deploy your project to your project"
sleep 2

echo "Please look for more info on our project page!"
sleep 2

echo "I'm trying to simulate a long script running... The stream will be sent as soon as we receive it!"
sleep 3

echo "Try to pass sequential params and you can check it here: $@"
sleep 3

echo "It gets more useful because this container has support for docker-cli, so you just need to mount your docker sock."
sleep 2

docker ps -a
sleep 2

echo "Easy, doesn't it?"
sleep 2

echo "Have fun!"
echo 2
