#!C:\Python311\python.exe  
#----------------------------------------------------------------------------
# Created By  : Allan Marcus
# Created Date: 2023-02-17
# version ='1.0'

# calculate a checksum for every file in a dir, recurively
# store results in a db
# check to see if anything has changed

# want to look into the database? I recommend HeidiSQL on Windows.

"""
To Do:
show deleted files, offer to purge records

reset deviations (delete rows)

option to change the base path for all the files in the database

"""

# underlying base code taken from 200_success at 
# https://codereview.stackexchange.com/questions/133859/write-md5-hashes-to-file-for-all-files-in-a-directory-tree

import csv
import hashlib
import zlib
import os
import pathlib
import time, datetime
import sqlite3
import argparse
import locale
import configparser
import math

# set up the global for the script's configs
# lazy, I know. Sue me. :-)
configDict = {}

def getConfig(pArgs):
    # get the basic configs for this run
    config = configparser.ConfigParser()
    
    configPath = os.path.realpath(configDict['configPath'])
    
    # see if the config file is there
    if not os.path.isfile(configPath):
        print('config file "' + configPath + '" is not there. Gotta have the config file. Please create it. Use -cc to create the basic file "checksum.ini".')
        exit() # not the most graceful, but what the heck
        
    #get the config items from the file
    config.read(configPath)
    # store the values in a dict that we will use throught the script
    configDict['configPath'] = configPath
    
    # path to the folder to monitor
    configDict['monitorDir'] = os.path.realpath(config['defaults']['monitor-Dir'])
    # validate
    if not os.path.isdir(configDict['monitorDir']):
        print('The path "' + configDict['monitorDir'] + '" is not valid. Cannot monitor what isn\'t there.')
        exit() # not the most graceful, but what the heck
    
    # folder path to store the DB file
    configDict['dbPath'] = os.path.realpath(config['defaults']['db-Path'])
    # validate
    if not os.path.isdir(configDict['dbPath']):
        print('The path "' + configDict['dbPath'] + '" is not valid. Cannot create the database file.')
        exit()

    # db file name
    configDict['dbFName'] = config['defaults']['db-file-name']
    if configDict['dbFName'] == '':
        print('Database file name in the config file is required.')
        exit()
    
    # set the full DBPath
    configDict['dbFullPath'] = os.path.join(configDict['dbPath'], configDict['dbFName'])
    
    # file extensions to ignore. Convert to a list
    configDict['ignoreExt'] = config['defaults']['ignore-Extensions'].upper().split(',')

def createConfigFile(pArgs):
    # create the basic config file then exit the script
    if not pArgs.create_config:
        return

    # path to the basic config file to create
    configPath = os.path.realpath(configDict['configPath'])
    
    if os.path.isfile(configPath):
        print('config file "' + configPath + '" is already there.')
        exit() # not the most graceful, but what the heck
    config = configparser.ConfigParser(allow_no_value=True)
    config.add_section('defaults')
    config.set('defaults', ' # The full path to the directory to monitor.')
    config.set('defaults', ' # example: C:\\Pictures\\Originals')
    config.set('defaults', ' # example: /users/joe/pictures/originals')
    config.set('defaults', 'monitor-Dir', 'path to dirctory to monitor')
    config.set('defaults', ' # Folder path to the database. The database file will be created when you run the script. Just the folder.')
    config.set('defaults', 'db-Path', 'database path here')
    config.set('defaults', ' # Database file name. The extension .db is commonly used')
    config.set('defaults', 'db-file-name', 'checksums.db')
    config.set('defaults', " # comma separated file extensions to ignore. Case doesn't master, but formating does")
    config.set('defaults', 'ignore-Extensions', "XMP,INI")

    with open(configPath, 'w') as configfile:
        config.write(configfile)
    print(configPath + " created. Please open the file and populate the values.")

    exit() # not the most graceful, but what the heck

def getConfigFilePath(pArgs):
    # get the path from the commandline
    # get the config_path if it was passed on the command line
    # if nothing is passed, the default is checksum.ini 
    configPath = pArgs.config_path
    
    # determine if this is a relative or absolute path
    if os.path.isabs(configPath):
        # this is an absolute path, so make sure it works
        configPath = os.path.realpath(configPath)
    else:
        # make this path relative from the script's dir
        pathToScript = os.path.realpath(os.path.dirname(__file__))
        configPath = os.path.join(pathToScript, configPath)
    
    return configPath

# for checksum checks
def file_hash_hex(file_path, hash_func):
    with open(file_path, 'rb') as f:
        return hash_func(f.read()).hexdigest() # use for SHA1 and the like
        
# for crc checks
def file_crc(file_path, hash_func):
    with open(file_path, 'rb') as f:
        return hash_func(f.read()) # use for CRC32

def recursive_file_listing(base_dir):
    for directory, subdirs, files in os.walk(base_dir):
        for filename in files:
            # ignore certain files
            extension = os.path.splitext(filename)[1].upper()
            if extension[1:] not in configDict['ignoreExt'] and filename != '.DS_Store':
                yield directory, filename, extension, os.path.join(directory, filename)

def db_setup(pDBCur):
    # set up the database if it needs to be set up

    # create the runlog table to hold info about runs
    sqlText = """
    CREATE TABLE IF NOT EXISTS runlog(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        monitor_dir, 
        db_path, 
        ignore_ext, 
        run_seconds,
        run_date datetime default CURRENT_TIMESTAMP,
        prg_args
        )"""
    # pDBCur.execute("drop table if exists runlog") # for debugging
    pDBCur.execute(sqlText)
    
    # create the checksum to hold checksums for each file
    sqlText = """
    CREATE TABLE IF NOT EXISTS checksum(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        path, 
        filename, 
        extension, 
        date_added datetime default CURRENT_TIMESTAMP,
        date_updated datetime,
        base_checksum_sha1, 
        base_checksum_crc32, 
        latest_checksum_sha1,
        latest_checksum_crc32,
    UNIQUE (path, filename))"""
    # pDBCur.execute("drop table if exists checksum") # for debugging
    pDBCur.execute(sqlText)
    
    # get the SQLite start time
    pDBCur.execute("select datetime(CURRENT_TIMESTAMP, 'localtime')")
    row = pDBCur.fetchone()
    return row[0]

def logrun(pCon, pDBCur, pRunSecs, pArgs):
    # insert the runlog data after the run
    sqlText = """
    insert into runlog (monitor_dir, db_path, ignore_ext, run_seconds, prg_args)
    VALUES (:monitorDir, :dbPath, :ignoreExt, :run_seconds, :args)
    """
    strArgs = str(vars(pArgs))
    toInsert = [{'monitorDir': configDict['monitorDir'], 'dbPath': configDict['dbFullPath'], 'ignoreExt': ', '.join(i for i in configDict['ignoreExt']), 'run_seconds': pRunSecs, 'args': strArgs}]
    pDBCur.executemany(sqlText, toInsert)
    pCon.commit()

def outputDataToCSV(pDBCur, pSQLtext, pFName, pHeaderRow):
    # make a full path for output files
    pathToScript = os.path.realpath(os.path.dirname(__file__))
    outputPath = os.path.join(pathToScript, pFName)

    # run a query and output the results to a csv file
    results = pDBCur.execute(pSQLtext)
    rows = results.fetchall()
    if len(rows) == 0:
        return ''
    else:
        with open(outputPath, 'w', encoding='UTF-8') as f:
            writer = csv.writer(f, dialect='unix')
            writer.writerow(pHeaderRow)
            writer.writerows(rows)
        return outputPath


def outputDuplicates (pDBCur, pArgs):
    # Search for any duplicate files bases on both checksums
    if not pArgs.duplicates:
        return
    sqlText = """
        SELECT PATH, filename, base_checksum_sha1 
        FROM checksum 
        WHERE base_checksum_sha1 IN 
        (SELECT base_checksum_sha1
            FROM checksum
            GROUP BY base_checksum_sha1, base_checksum_crc32
            HAVING COUNT(*) > 1)
        order by base_checksum_sha1"""
    results = outputDataToCSV(pDBCur, sqlText, 'duplicates.csv', ['path', 'filename', 'base_checksum_sha1'])
    if results == '':
        print("No duplicates found. If the checksum is the same for two files, it's likely those are the same files.")
    else:
        print("Duplicates written to file: " + results)
    
def outputFailures(pDBCur, pArgs):
    # output the deviaions 
    # if nothing to output, return now
    if not pArgs.failures:
        return
    sqlText = """
        SELECT id, path, filename, extension, base_checksum_sha1, latest_checksum_sha1, 
        base_checksum_crc32, latest_checksum_crc32, datetime(date_added, 'localtime'), 
        datetime(date_updated, 'localtime') 
        FROM checksum
        where (base_checksum_sha1 != latest_checksum_sha1) or (base_checksum_crc32 != latest_checksum_crc32)"""
    toPrint = "Checksum report for files with a deviation. Recommend you restore these files from back up:"
    results = outputDataToCSV(pDBCur, sqlText, 'all_files.csv', ['id', 'path', 'filename', 'extension', 'base_checksum_sha1', 'latest_checksum_sha1', 'base_checksum_crc32', 'latest_checksum_crc32', 'date_added', 'date_updated'])
    if results == '':
        print('No failures detected. Checked {:,} files.'.format(getTotalRows(pDBCur)))
    else:
        print("Checksum report for files with a deviation. Recommend you restore these files from back up. Report written to file: " + results)

def outputAll(pDBCur, pArgs):
    # output all
    # if nothing to output, return now
    if not pArgs.all_rows:
        return
    sqlText = """
        SELECT id, path, filename, extension, base_checksum_sha1, latest_checksum_sha1, 
        base_checksum_crc32, latest_checksum_crc32, datetime(date_added, 'localtime'), 
        datetime(date_updated, 'localtime') 
        FROM checksum"""
    results = outputDataToCSV(pDBCur, sqlText, 'all_files.csv', ['id', 'path', 'filename', 'extension', 'base_checksum_sha1', 'latest_checksum_sha1', 'base_checksum_crc32', 'latest_checksum_crc32', 'date_added', 'date_updated'])
    if results == '':
        print("No records found. ")
    else:
        print("Data written to file: " + results)

def outputRunLogs(pDBCur, pArgs):
    # output all the runs from the runlog
    if not pArgs.run_log:
        return
    sqlText = "SELECT id, monitor_dir, db_path, ignore_ext, run_seconds, datetime(run_date, 'localtime'), prg_args FROM runlog"
    results = outputDataToCSV(pDBCur, sqlText, 'runlog.csv', ['id', 'monitor_dir', 'db_path', 'ignore_ext', 'run_seconds', 'run_date', 'prg_args'])
    if results == '':
        print("No records found. ")
    else:
        print("Data written to file: " + results)

def updateChecksum(pCon, pDBCur, pDir, pFName, pExt, pPath):
    # add or update the record for the file
    
    # get the SHA1
    sha1 = file_hash_hex(pPath, hashlib.sha1)
    
    # get the CRC64
    crc = file_crc(pPath, zlib.crc32)
    
    sqlText = """
    insert into checksum (path, filename, extension, 
        base_checksum_sha1, base_checksum_crc32, latest_checksum_sha1, latest_checksum_crc32,
        date_updated)
    VALUES (:p, :fn, :ext, :sha1, :crc,  :sha1, :crc, CURRENT_TIMESTAMP)
    ON CONFLICT (path, filename) DO UPDATE SET latest_checksum_sha1 = :sha1, latest_checksum_crc32 = :crc, date_updated = CURRENT_TIMESTAMP
    """
    toInsert = [{'p': pDir , 'fn': pFName, 'ext': pExt, 'sha1': sha1, 'crc': crc }]
    pDBCur.executemany(sqlText, toInsert)
    pCon.commit()

def arg_parse():
    # See if there are arguments on the command line
    parser = argparse.ArgumentParser(description='Write checksums for all files in a directory to a database. Recommended options: -vv -p -f')
    
    groupVerbose = parser.add_mutually_exclusive_group()
    groupVerbose.add_argument('-v', "--verbose", help="Show directory names as they are processed", action="store_true")
    groupVerbose.add_argument('-vv', "--very_verbose", help="Show directory names and a . for each files as processed", action="store_true")
    parser.add_argument('-r', "--report_only", help="Report only, do not process files", action="store_true")
    parser.add_argument('-p', "--proc_time", help="Output file processing time (in seconds)", action="store_true")
    parser.add_argument('-rl', "--run_log", help="Output the run log records", action="store_true")
    parser.add_argument('-f', "--failures", help="Output the checksum failures (files to restore) to a csv file in the same DIR as the script", action="store_true")
    parser.add_argument('-a', "--all_rows", help="Output all the checksum records to a csv file in the same DIR as the script", action="store_true")
    parser.add_argument('-d', "--duplicates", help="Output potential duplicate files to a csv file in the same DIR as the script", action="store_true")
    parser.add_argument('-db', "--db_stats", help="Output various stats from the database", action="store_true")
    parser.add_argument('-cc', "--create_config", help="Create the config INI file in the same DIR as the script", action="store_true")
    parser.add_argument("config_path", type=str, help='Optional: path to config file for this script. Defaults to checksum.ini in script\'s dir', nargs='?', default='checksum.ini')
    
    args = parser.parse_args()
    # print(args) # debug
    return(args)

def getTotalRows(pDBCur):
        # rows in the checksum table
        pDBCur.execute("select count(*) from checksum")
        row = pDBCur.fetchone()
        return row[0]

def outputDBStats(pDBCur, pArgs):
    # show some stats of the db and the data
    if pArgs.db_stats:
        print('Database Statistics:')
        
        # rows in the runlog table
        pDBCur.execute("select count(*) from runlog")
        row = pDBCur.fetchone()
        runlogRows = row[0]
        print('Program Runs: {}'.format(runlogRows))

        # rows in the checksum table
        print('Total files being tracked: {:,}'.format(getTotalRows(pDBCur)))

        # potential duplicates
        sqlText = """
            SELECT count(*) 
            FROM checksum 
            WHERE base_checksum_sha1 IN 
            (SELECT base_checksum_sha1
                FROM checksum
                GROUP BY base_checksum_sha1, base_checksum_crc32
                HAVING COUNT(*) > 1)
            order by base_checksum_sha1;"""
        pDBCur.execute(sqlText)
        row = pDBCur.fetchone()
        checksumRows = row[0]
        print('Potential Duplicates: {}'.format(checksumRows))
        
        # files by extension
        exts = pDBCur.execute("select extension, count(*) from checksum group by extension")
        runResults = exts.fetchall()
        print("Files being tracked by extension")
        for r in runResults:
            print (' {}: {:,}'.format(r[0],r[1]))
        
        print('Database path: ' + configDict['dbFullPath'])
        print('Directory with files to monitor: ' + configDict['monitorDir'])
        print('File extensions to ignore: ' + str(configDict['ignoreExt']))

def main():

    # start by getting toe command line parameters
    args = arg_parse()
    
    # get the config path and put itinto the configDict global
    configDict['configPath'] = getConfigFilePath(args)
    
    # if the param to create the config file is passed, do it first and exit
    createConfigFile(args)
    
    # get the scripts config INI values
    getConfig(args)

    # Grab Currrent Time Before Running the Code
    start = time.time()

    # set up the db
    db_connection = sqlite3.connect(configDict['dbFullPath'])
    db_cursor = db_connection.cursor()
    #db_connection.set_trace_callback(print) # debug
    dbStartTime = db_setup(db_cursor)    

    if not args.report_only:
        # count the file for progress reporting
        totalFiles = 0
        for directory, filename, extension, path in recursive_file_listing(configDict['monitorDir']):
            totalFiles += 1
        print(totalFiles)
    
        count = 0
        lastDir = ''
        for directory, filename, extension, path in recursive_file_listing(configDict['monitorDir']):
            count += 1
            if directory != lastDir and (args.verbose or args.very_verbose):
                # calculate the remaining time
                checkpoint = time.time()
                elapsed = checkpoint - start
                complete = count/totalFiles
                estimated = elapsed / complete
                remaining = estimated - elapsed
                hours = math.floor(remaining / 60 / 60)
                minutes = math.floor(remaining / 60)
                seconds = int(remaining % 60)
                old_time = datetime.datetime.now()
                new_time = old_time + datetime.timedelta(seconds = remaining)
                print('\n{0} of {1} - {2:2.2f}% complete - Estimate time left (H:M:S): {3:02d}:{4:02d}:{5:02d} - Est Completion: {6}'.format(count, totalFiles, complete*100,hours, minutes, seconds,new_time.strftime('%H:%M:%S')))

                print('Processing: ' + directory + '.', end='', flush=True)
            else:
                if args.very_verbose:
                    print('.', end='', flush=True)
            lastDir = directory
            updateChecksum(db_connection,db_cursor, directory, filename, extension, path) 

    # Grab Currrent Time After Running the Code
    end = time.time()
    #Subtract Start Time from The End Time
    total_time = end - start
    if args.proc_time:
        print("\nProcessing time: "+ str(round(total_time)) + " seconds")
    
    # log the run
    logrun (db_connection, db_cursor, total_time, args)
    
    outputRunLogs(db_cursor, args)
    outputAll(db_cursor, args)
    outputFailures(db_cursor, args)
    outputDuplicates(db_cursor, args)
    outputDBStats(db_cursor, args)

if __name__ == "__main__":
    main()