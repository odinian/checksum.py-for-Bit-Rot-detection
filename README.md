# checksums.py
A python script to store and compare checksums to reveal file corruption like bit rot.
 
Discussion of bit rot is way beyond this readme file, so Google it learn more.

# Requirements
This script should work on any system that can run Python 3. For Windows you might install Python from the Microsoft Store.

# Getting Started
Download the script and run it with the -cc option to create the default config file "checksum.ini" in the same folder as the script.

cd to the script's directory to create the INI config file.
> python3 checksums.py -cc

Edit the config file with any text editor and set three basic pieces of info:
* The path to folder to monitor
* The path to the folder where the SQLite database will be stored
* Any file extensions to ignore

then run the script to calculate and store the checksums. On my system (AMD5800x with NVME drive) it takes about 21 minutes to process 35000 images.
cd to the script's directory
> python3 checksums.py -vv -p -f

I'm not sure how to set the she-bang line for all platforms. Any help is appreciated.

# Assumptions
This script was written to check the file integrity of a photos folder, but can work with any folder containing data the never changes. The assumption is the files in the folder never change, except when new files are added. If XML sidecar files or other files are written to the folder (or sub-folders), they can be ignored by file extension.

Files stored for years on the same disk may become corrupted due to bit rot or other issues. Even with a good backup plan, you want to know if the file on disk isn't the same as it was when you backed it up. Backup programs commonly use the *file modified date* to determine if a file has changed, but bit rot or corruption will happen under the hood, thus the file modified date will not change.

# How It Works

## About checksums
A little about [checksums](https://en.wikipedia.org/wiki/Checksum). A checksum is a string or number calculated by an algorithm that produces consistent output for each file. If the file has changed, the resultant checksum should be different. This is how the script *should* be able to detect any change to the file. Checksums are commonly used to ensure data and files are transmitted correctly. The better the checksum, the less likely two files will have the same resultant checksum values, therefore checksums used for security are designed to reveal a different checksum if a file was maliciously altered. 

For our purposes we are just trying to determine if the file was altered by bit rot or other corruption. We just want to detect a file change. 

## About the script

The script will calculate two checksums for each file, then store those checksums in a SQLite database. You don't need to worry about management of the database; it's a single file on your drive and you set its path int he config file. When you run the script again, the checksums are calculated again and written in the database along side the original checksums. At the end of the script, files where the checksums don't match are written to a CSV file. You should probably restore these files and run the script again to ensure the original file is there.

The script calculates two checksums per file. CRC-32 and SHA-1. 

## Duplicate files

Since a checksum should be unique for each file, the possibility of a collision, where two files have the same checksum, is slim. As a result, the script can output a CSV file where two or more files have matching checksums. Those files are likely duplicates and you can address them as you see fit.

# Options

Run the script with "-h" to see this help

```plaintext
usage: checksum.py [-h] [-v | -vv] [-r] [-p] [-rl] [-f] [-a] [-d] [-db] [-cc] [config_path]

Write checksums for all files in a directory to a database. Recommended options: -vv -p -f

positional arguments:
  config_path           Optional: path to config file for this script. Defaults to checksum.ini in script's dir

options:
  -h, --help            show this help message and exit
  -v, --verbose         Show directory names as they are processed
  -vv, --very_verbose   Show directory names and a . for each files as processed
  -r, --report_only     Report only, do not process files
  -p, --proc_time       Output file processing time (in seconds)
  -rl, --run_log        Output the run log records
  -f, --failures        Output the checksum failures (files to restore) to a csv file in the same DIR as the script
  -a, --all_rows        Output all the checksum records to a csv file in the same DIR as the script
  -d, --duplicates      Output potential duplicate files to a csv file in the same DIR as the script
  -db, --db_stats       Output various stats from the database
  -cc, --create_config  Create the config INI file in the same DIR as the script
```
## config_path
There are two ways to control the options in the program. The command line options and contents of the config file. If no config file path is passed on the command line, the default is look int he same directory as the script for a file called checksums.ini

## Verbosity
The script will run silent (not give any progress) when running unless one of the two verbose options is use. "-v" will print the sub-folder being processed. "-vv" will add a period "." after the folder name as the script process each file. This give the user a little feedback to know the script is working.

## Report Only
The "-r" option will suppress file processing. Use "-r" if you want to quickly use any of the output options.

## Run Log
Every time the script is run, a log of the run is added to the database. This option will export that log to a CSV in the same folder as the script.

## Failures
Export a list of files to a CSV in the same folder as the script where the checksums do not match. These files a very susspect and likely should be restored from back up and checksumed again.

## All Rows
Export the entire filelist to a CSV in the same folder as the script.

## Duplicates
Export a list of likely duplicate files to a CSV in the same folder as the script.

## DB Stats
Output some (mildy) interested stats about the files in the database.

## Create Config
Will create an empty config file at with the default path, or the path passed to the script. Will not overwrite a file already there.