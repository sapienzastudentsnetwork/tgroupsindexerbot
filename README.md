# Sapienza Students Bot

## About the project

[Sapienza Students Bot](https://t.me/SapienzaStudentsBot) was born out of the need, in its time by Sapienza Students, and today by Sapienza Students Network, to promote and make the Telegram groups of students of different courses and their different subjects more easily discoverable from other prospective students

### Current project status

The goal of this first version was to make all the groups previously available in the GO instance available again, but there is still a long way to go, since the main functionality, which consists of the bot's users being able to add the bot to a group and make it indexed by choosing a category (e.g. a degree course) and a sub-category, is still to be implemented. The anti-spam features offered by the previous solution in GO are not a priority at the moment (given also the existence for this purpose of much more established bots such as https://t.me/MissRose_bot and https://t.me/GroupHelpBot), while we would also like to re-introduce the system of assigning a new admin for groups in which the creator has deleted his Telegram account; as well as some useful commands and shortcuts for administrators and users to use within groups.

### The reason behind the choice of Python as programming language

Initially Sapienza Students opted for a solution in the GO programming language (whose code is still available on [GitLab](https://gitlab.com/sapienzastudents/antispam-telegram-bot)), recently, with the management of the bot entrusted to [Matypist](https://github.com/matypist) and [Sapienza Students Network](https://github.com/sapienzastudentsnetwork), it was decided to rewrite the bot from scratch in Python. The reason behind this choice is that Python is a mandatory subject in the Computer Science course at Sapienza, mainly through the teaching of "Fondamenti di Programmazione" in the first  semester of the first year of the course, as well as in other Computer Science-related courses available at Sapienza and also most other Italian universities, whereas GO is actually usually only found in teachings at the student's choice. The new aim was therefore the choice of a programming language within the reach of most of the students who will then actually use the bot, so as to facilitate any voluntary collaboration in its development.

## Deploy your own instance

### Prerequisites

1. Create your bot instance on BotFather

    1. Launch https://t.me/BotFather on Telegram

    2. Send `/newbot` to https://t.me/BotFather on Telegram

    3. Follow the prompts to choose a name and username for your bot instance

    4. Once you are done following the instructions, you should receive a token in the final confirmation message

2. Create your PostgreSQL instance

   a. Get an instance hosted for free by ElephantSQL

      1. Go to https://customer.elephantsql.com/signup

      2. Enter your email address

      3. Check your inbox for a confirmation mail from ElephantSQL

      4. Open the link contained in the confirmation mail to open the account creation page

      5. Enter a password of your choosing and check the "Yes" checkbox to accept the Terms of Service

      6. Click the "Create Account" button

      7. Click the "Create New Instance" button and follow the instructions to name, set up and create your instance

      8. Once created, go to the Instance Panel (https://customer.elephantsql.com/instance/) and access the instance

      9. In the instance details page, copy the postgres:// URL with the copy icon

5. Install python3 and python3-pip on your operating system

   - Windows (not tested)

     - Download Python3 from the [official website](https://www.python.org/downloads/windows/)
     - Run the installer and follow the prompts to install Python3 on your system
     - Open the Command Prompt and type `python3 -m ensurepip --upgrade` to install python3-pip
   
   - Debian-based GNU/Linux distributions

     - Open the terminal and run the command `sudo apt update` to update the package lists
     - Run the command `sudo apt install python3 python3-pip` to install Python3 and python3-pip

   - Arch Linux

     - Open the terminal and run the command `sudo pacman -Syu` to update the package lists
     - Run the command `sudo pacman -S python python-pip` to install Python3 and python3-pip

6. Verify that python3 and python3-pip are installed by running the command `python3 -V` and `pip3 -V` respectively