import json
import os
import asyncio
from slack_sdk import WebClient
from datetime import datetime as dt
from dotenv import load_dotenv


def getCredz():
    load_dotenv()
    userToken = os.getenv('userToken')
    client = WebClient(token=userToken)

    with open('tasks.json', 'r', encoding='utf-8') as j:
        tasks = json.load(j)

    return client, tasks


async def slackMsg(client, channel, msg):
    response = client.chat_postMessage(
        channel=channel,
        text=msg
    )

    return response['ts']


async def checkReply(client, channel, reply, ts):
    # Include fail safe for 'thread_not_found --->
    response = client.conversations_replies(
        channel=channel,
        ts=ts,
        inclusive=True
    )

    # Ensure 'messages' exists and is a list
    msgs = response.get('messages', [])
    if not msgs:
        print("❌ No messages found at or after the given timestamp!")
        return None

    for msg in msgs:
        # print(f"Checking Message: {msg['text']}")
        if 'text' in msg and reply.lower() in msg['text'].lower():
            print(f"✅ Response Received")
            return msg['text']

    print("❌ No text response received!")
    return None


async def tasksPitch(client, tasks, task):
    subseq = tasks[task]['SubseqReminder']
    inChannel = tasks[task]['SourceChannel']
    outChannel = tasks[task]['StorageChannel']
    replTemp = tasks[task]['ReplTemp']
    inMsg = tasks[task]['inMsg']
    outMsg = tasks[task]['outMsg']

    print(f"[{dt.now().strftime('%H:%M:%S')}] Starting task for {task}")

    ts = await slackMsg(client, inChannel, inMsg)
    print(f"Message sent to {inChannel} for {task}")

    reply = None
    while not reply:
        await asyncio.sleep(subseq*60)
        reply = await checkReply(client, inChannel, replTemp, ts)

        if not reply:
            print(
                f"[{dt.now().strftime('%H:%M:%S')}] ❌ Reply not found, sending reminder for {task}.")
            ts = await slackMsg(client, inChannel, inMsg)
            await asyncio.sleep(subseq*60)

    # Once the reply is received
    print(f"[{dt.now().strftime('%H:%M:%S')}] ✅ Reply received: {reply}")
    await slackMsg(client, outChannel, outMsg)


async def scheduleTasks(client, tasks, task, schTime=None):
    """Schedule and run a task, either immediately or at the scheduled time"""
    if schTime:
        # Calculate time until shceduled execution
        rn = dt.now()
        hr, mn = map(int, schTime.split(':'))
        target = rn.replace(hour=hr, minute=mn, second=0, microsecond=0)

        # If target time is in the past, schedule for tomorrow
        if target < rn:
            secondUntil = (target.timestamp()+86400) - rn.timestamp()
        else:
            secondUntil = target.timestamp() - rn.timestamp()

        print(f"[{dt.now().strftime('%H:%M:%S')}] Task '{task}' will run in {secondUntil:.1f} seconds (at {schTime})")
        await asyncio.sleep(secondUntil)

    # Run the task
    await tasksPitch(client, tasks, task)


async def main():
    print("Starting task check...")
    client, tasks = getCredz()

    taskCorouts = []

    for task, config in tasks.items():
        hr = int(config['InitHour'])
        mn = int(config['InitMin'])

        schTime = f"{hr:02d}:{mn:02d}"

        # Add each task to our list of coroutines
        taskCorouts.append(
            scheduleTasks(client, tasks, task, schTime)
        )
        print(f"Scheduled task '{task}' at {schTime}")

    # Run all tasks concurrently
    await asyncio.gather(*taskCorouts)


if __name__ == '__main__':
    asyncio.run(main())
