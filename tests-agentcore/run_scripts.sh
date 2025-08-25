#!/bin/bash

echo "updating token and initializing environment variables"
. .env && \
echo && \
echo && \
echo ******************************* && \
echo ** Running unit tests        ** && \
echo ******************************* && \
echo && \
echo && \
pytest -x -s -v unit/test_agentcore* && \
# cd ../integration && \
# echo ******************************* && \
# echo ** Running integration tests ** && \
# echo ******************************* && \
# echo && \
# echo && \
# pytest -x -s -v . && \
echo ******************************* && \
echo ** Running system tests      ** && \
echo ******************************* && \
echo && \
echo && \
pytest -x -s -v system/test_agentcore* && \
echo All tests completed successfully!

