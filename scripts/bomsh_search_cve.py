#! /bin/env python3
# Copyright (c) 2022 Cisco and/or its affiliates.
#
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at:
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Bomsh script to search CVEs for binaries or find affected binaries for CVEs.

Based upon the gitBOM artifact tree or gitBOM docs generated by Bomsh or Bomtrace.

December 2021, Yongkui Han
"""

import argparse
import sys
import os
import subprocess
import json
import re

# for special filename handling with shell
try:
    from shlex import quote as cmd_quote
except ImportError:
    from pipes import quote as cmd_quote

TOOL_VERSION = '0.0.1'
VERSION = '%(prog)s ' + TOOL_VERSION

LEVEL_0 = 0
LEVEL_1 = 1
LEVEL_2 = 2
LEVEL_3 = 3
LEVEL_4 = 4

args = None
g_cvedb = None
g_checksum_db = None
g_metadata_db = None

g_tmpdir = "/tmp"
g_jsonfile = "/tmp/bomsh_search_jsonfile"

#
# Helper routines
#########################
def verbose(string, level=1, logfile=None):
    """
    Prints information to stdout depending on the verbose level.
    :param string: String to be printed
    :param level: Unsigned Integer, listing the verbose level
    :param logfile: file to write
    """
    if args.verbose >= level:
        if logfile:
            append_text_file(logfile, string + "\n")
        # also print to stdout
        print(string)


def write_text_file(afile, text):
    '''
    Write a string to a text file.

    :param afile: the text file to write
    '''
    with open(afile, 'w') as f:
         return f.write(text)


def append_text_file(afile, text):
    '''
    Append a string to a text file.

    :param afile: the text file to write
    '''
    with open(afile, 'a+') as f:
         return f.write(text)


def read_text_file(afile):
    '''
    Read a text file as a string.

    :param afile: the text file to read
    '''
    with open(afile, 'r') as f:
         return (f.read())


def get_shell_cmd_output(cmd):
    """
    Returns the output of the shell command "cmd".

    :param cmd: the shell command to execute
    """
    #print (cmd)
    output = subprocess.check_output(cmd, shell=True, universal_newlines=True)
    return output


def get_filetype(afile):
    """
    Returns the output of the shell command "file afile".

    :param afile: the file to check its file type
    """
    cmd = "file " + cmd_quote(afile) + " || true"
    #print (cmd)
    output = subprocess.check_output(cmd, shell=True, universal_newlines=True)
    res = re.split(":\s+", output.strip())
    if len(res) > 1:
        return ": ".join(res[1:])
    return "empty"


def load_json_db(db_file):
    """ Load the the data from a JSON file

    :param db_file: the JSON database file
    :returns a dictionary that contains the data
    """
    db = dict()
    with open(db_file, 'r') as f:
        db = json.load(f)
    return db


def save_json_db(db_file, db, indentation=4):
    """ Save the dictionary data to a JSON file

    :param db_file: the JSON database file
    :param db: the python dict struct
    :returns None
    """
    if not db:
        return
    print ("save_json_db: db file is " + db_file)
    try:
        f = open(db_file, 'w')
    except IOError as e:
        print ("I/O error({0}): {1}".format(e.errno, e.strerror))
        print ("Error in save_json_db, skipping it.")
    else:
        with f:
            json.dump(db, f, indent=indentation, sort_keys=True)


############################################################
#### End of helper routines ####
############################################################


def get_git_file_hash(afile):
    '''
    Get the git object hash value of a file.
    :param afile: the file to calculate the git hash or digest.
    '''
    cmd = 'git hash-object ' + cmd_quote(afile) + ' || true'
    #print(cmd)
    output = get_shell_cmd_output(cmd)
    #verbose("output of git_hash:\n" + output, LEVEL_3)
    if output:
        return output.strip()
    return ''


def get_git_files_hash(afiles):
    '''
    Get the git hash of a list of files.
    :param afiles: the files to calculate the git hash or digest.
    '''
    hashes = {}
    for afile in afiles:
        hashes[afile] = get_git_file_hash(afile)
    return hashes


def is_archive_file(afile):
    """
    Check if a file is an archive file.

    :param afile: String, name of file to be checked
    :returns True if the file is archive file. Otherwise, return False.
    """
    return get_filetype(afile) == "current ar archive"


def is_jar_file(afile):
    """
    Check if a file is a Java archive file.

    :param afile: String, name of file to be checked
    :returns True if the file is JAR file. Otherwise, return False.
    """
    return " archive data" in get_filetype(afile)


def get_embedded_bom_id_of_archive(afile):
    '''
    Get the embedded 20bytes githash of the associated gitBOM doc for an archive file.
    :param afile: the file to extract the 20-bytes embedded .bom archive entry.
    '''
    abspath = os.path.abspath(afile)
    cmd = 'cd ' + g_tmpdir + ' ; rm -rf .bom ; ar x ' + cmd_quote(abspath) + ' .bom 2>/dev/null || true'
    #print(cmd)
    output = get_shell_cmd_output(cmd)
    bomfile = os.path.join(g_tmpdir, ".bom")
    if os.path.exists(bomfile):
        return get_shell_cmd_output('xxd -p ' + bomfile + ' || true').strip()
    return ''


def get_embedded_bom_id_of_jar_file(afile):
    '''
    Get the embedded 20bytes githash of the associated gitBOM doc for a .jar file.
    :param afile: the file to extract the 20-bytes embedded .bom archive entry.
    '''
    abspath = os.path.abspath(afile)
    cmd = 'cd ' + g_tmpdir + ' ; rm -rf .bom ; jar xf ' + cmd_quote(abspath) + ' .bom 2>/dev/null || true'
    #print(cmd)
    output = get_shell_cmd_output(cmd)
    bomfile = os.path.join(g_tmpdir, ".bom")
    if os.path.exists(bomfile):
        return get_shell_cmd_output('xxd -p ' + bomfile + ' || true').strip()
    return ''


def get_embedded_bom_id_of_elf_file(afile):
    '''
    Get the embedded 20bytes githash of the associated gitBOM doc for an ELF file.
    :param afile: the file to extract the 20-bytes embedded .bom ELF section.
    '''
    abspath = os.path.abspath(afile)
    cmd = 'readelf -x .bom ' + cmd_quote(afile) + ' 2>/dev/null || true'
    output = get_shell_cmd_output(cmd)
    if not output:
        return ''
    lines = output.splitlines()
    if len(lines) < 3:
        return ''
    result = []
    for line in lines:
        tokens = line.strip().split()
        if len(tokens) > 5 and tokens[0] == "0x00000000":
            result.extend( (tokens[1], tokens[2], tokens[3], tokens[4]) )
        elif len(tokens) > 2 and tokens[0] == "0x00000010":
            result.append(tokens[1])
            break
    return ''.join(result)


def get_embedded_bom_id(afile):
    '''
    Get the embedded 20bytes githash of the associated gitBOM doc for a binary file.
    :param afile: the file to extract the 20-bytes embedded .bom section.
    returns a string of 40 characters
    '''
    if is_archive_file(afile):
        return get_embedded_bom_id_of_archive(afile)
    elif is_jar_file(afile):
        return get_embedded_bom_id_of_jar_file(afile)
    else:
        return get_embedded_bom_id_of_elf_file(afile)


# the file blob checksum (blob_id) => gitBOM doc (bom_id) mapping cache DB.
g_gitbom_doc_db = {}

def create_gitbom_node_of_blob_id(afile):
    '''
    Create the gitBOM hash-tree node from a gitBOM doc.
    :param afile: a single gitBOM doc storing a list of githashes and bom identifiers.
    returns a list of checksum (blob_id).
    '''
    result = []
    content = read_text_file(afile)
    lines = content.splitlines()
    for line in lines:
        tokens = line.split()
        if len(tokens) >= 2 and tokens[0] == "blob":
            result.append(tokens[1])
        if len(tokens) == 4 and tokens[0] == "blob" and tokens[2] == "bom":
            # Add its corresponding gitBOM doc to the cache DB, which is required to find corresponding bom_id for a blob_id
            g_gitbom_doc_db[tokens[1]] = tokens[3]
    return result


def create_gitbom_node_of_bom_id(afile):
    '''
    Create the gitBOM hash-tree node from a gitBOM doc.
    :param afile: a single gitBOM doc storing a list of githashes and bom identifiers.
    returns a list of gitBOM doc (bom_id).
    '''
    result = []
    content = read_text_file(afile)
    lines = content.splitlines()
    for line in lines:
        tokens = line.split()
        if len(tokens) == 2 and tokens[0] == "blob":
            result.append(tokens[1])
        elif len(tokens) == 4 and tokens[0] == "blob" and tokens[2] == "bom":
            result.append(tokens[3])
    return result


def create_gitbom_node_of_checksum_line(afile):
    '''
    Create the gitBOM hash-tree node from a gitBOM doc.
    :param afile: a single gitBOM doc storing a list of githashes and bom identifiers.
    returns a list of checksum lines inside the gitBOM doc.
    '''
    content = read_text_file(afile)
    return content.strip().splitlines()


def get_node_id_from_checksum_line(checksum_line):
    '''
    Get the gitBOM hash-tree node ID from a line in the gitBOM doc.
    The checksum line can be: 40-character SHA1 checksum, "blob SHA1", or "blob SHA1 bom SHA1"
    :param checksum_line: the checksum line provided
    returns the node ID, which is bom_id if bom_id exists, otherwise, the blob_id
    '''
    if " bom " in checksum_line:
        return checksum_line[50:90]
    elif "blob " == checksum_line[:5]:
        return checksum_line[5:45]
    return checksum_line.strip()


def get_all_gitbom_doc_files(object_bomdir):
    '''
    Get all the gitBOM doc files stored in object_bomdir
    :param object_bomdir: the gitBOM object directory to store all gitBOM docs
    returns a list of gitBOM doc files and its associated githash
    '''
    entries = os.listdir(object_bomdir)
    for entry in entries:
        if not len(entry) == 2:
            continue
        adir = os.path.join(object_bomdir, entry)
        if not os.path.isdir(adir):
            continue
        for afile in os.listdir(adir):
            ahash = entry + afile
            gitbom_doc_file = os.path.join(adir, afile)
            yield gitbom_doc_file, ahash


def create_gitbom_doc_treedb(object_bomdir, use_checksum_line=True):
    '''
    Create the gitBOM doc hash-tree DB from all the gitBOM docs in the bomdir.
    :param object_bomdir: the gitBOM object directory to store all gitBOM docs
    :param use_checksum_line: a flag to use the full checksum line as node of treedb
    returns a dict with bom_id as key (if no bom_id, then use checksum (blob_id) as key)
    '''
    treedb = {}
    if not os.path.isdir(object_bomdir):
        return treedb
    for afile, ahash in get_all_gitbom_doc_files(object_bomdir):
        if use_checksum_line:
            node = create_gitbom_node_of_checksum_line(afile)
        else:
            node = create_gitbom_node_of_bom_id(afile)
        # can only use bom_id as key, since the associated checksum is unknown
        # CVEs are usually associated with leaf nodes only, so this should still work
        treedb[ahash] = {"hash_tree": node}
    return treedb


def update_gitbom_doc_treedb_for_bomid(object_bomdir, checksum, bom_id, treedb):
    '''
    Update/create the gitBOM doc hash-tree DB for a single bom_id, from the gitBOM docs in the bomdir.
    This function recurses on itself.
    :param object_bomdir: the gitBOM object directory to store all gitBOM docs
    :param checksum: the git checksum of the file that is associated with bom_id
    :param bom_id: a single bom_id that is embedded in binary file
    :param treedb: the dict to update with checksum as key
    returns a dict with checksum (blob_id) as key (even if bom_id exists for blob_id)
    '''
    if checksum in treedb:
        return treedb
    afile = os.path.join(object_bomdir, bom_id[:2], bom_id[2:])
    if not os.path.exists(afile):
        return treedb
    node = create_gitbom_node_of_blob_id(afile)
    if not node:
        return treedb
    # Use checksum (not bom_id) as key of treedb, as cvedb is keyed with checksum
    treedb[checksum] = {"hash_tree": node}
    for entry in node:
        if entry in g_gitbom_doc_db:
            update_gitbom_doc_treedb_for_bomid(object_bomdir, entry, g_gitbom_doc_db[entry], treedb)
    return treedb


def get_blob_bom_id_from_checksum_line(checksum_line):
    '''
    Extract blob_id, bom_id from the checksum line.
    The checksum line can be: 40-character SHA1 checksum, "blob SHA1", or "blob SHA1 bom SHA1"
    :param checksum_line: the checksum line provided
    '''
    if checksum_line[:5] == "blob ":
        return (checksum_line[5:45], checksum_line[50:90])
    return (checksum_line.strip(), '')


def update_gitbom_doc_treedb_for_checksum_line(object_bomdir, checksum, bom_id, treedb):
    '''
    Update/create the gitBOM doc hash-tree DB for a single bom_id, from the gitBOM docs in the bomdir.
    This function recurses on itself.
    :param object_bomdir: the gitBOM object directory to store all gitBOM docs
    :param checksum: the git checksum (blob_id) of the file that is associated with bom_id
    :param bom_id: a single bom_id that is embedded in binary file
    :param treedb: the dict to update with bom_id as key
    returns a dict with bom_id as key (if no bom_id, then use checksum (blob_id) as key)
    '''
    if bom_id in treedb:
        return treedb
    afile = os.path.join(object_bomdir, bom_id[:2], bom_id[2:])
    if not os.path.exists(afile):
        return treedb
    node = create_gitbom_node_of_checksum_line(afile)
    if not node:
        return treedb
    # Use bom_id (not blob_id) as key for treedb.
    # CVEs are usually associated with leaf nodes only, so this should still work
    treedb[bom_id] = {"hash_tree": node}
    for line in node:
        blobid, bomid = get_blob_bom_id_from_checksum_line(line)
        if bomid:
            update_gitbom_doc_treedb_for_checksum_line(object_bomdir, blobid, bomid, treedb)
    return treedb


def create_gitbom_doc_treedb_for_files(bomdir, afiles, use_checksum_line=True):
    '''
    Create the gitBOM doc hash-tree DB for a list of files, from the gitBOM docs in the bomdir.
    :param bomdir: the gitBOM repo directory to store all gitBOM docs and metadata
    :param afiles: a list of files which contain embedded .bom section
    :param use_checksum_line: a flag to use the full checksum line as node of treedb
    returns a dict with checksum (blob_id) as key (even if bom_id exists for blob_id)
    '''
    bom_db = {}
    jsonfile = os.path.join(bomdir, "metadata", "bomsh", "bomsh_gitbom_doc_mapping")
    if os.path.exists(jsonfile):
        bom_db = load_json_db(jsonfile)
    object_bomdir = os.path.join(bomdir, "objects")
    treedb = {}
    for afile in afiles:
        checksum = get_git_file_hash(afile)
        bom_id = get_embedded_bom_id(afile)
        if not bom_id:
            print("Warning: No embedded .bom section in file: " + afile)
            if bom_db and checksum in bom_db:
                bom_id = bom_db[checksum]
                print("From recorded gitBOM mappings, found bom_id " + bom_id + " for file: " + afile)
            if not bom_id:
                print("Warning: No recorded bom_id mapping for file: " + afile)
                continue
        verbose("blob_id: " + checksum + " bom_id: " + bom_id + " file: " + afile)
        if use_checksum_line:
            # Add below blob_id to bom_id mapping for convenience
            treedb[checksum] = {"hash_tree": [bom_id,]}
            update_gitbom_doc_treedb_for_checksum_line(object_bomdir, checksum, bom_id, treedb)
        else:
            update_gitbom_doc_treedb_for_bomid(object_bomdir, checksum, bom_id, treedb)
    return treedb

############################################################
#### End of embedded .bom section handling routines ####
############################################################


def get_metadata_for_checksum_from_db(db, checksum, which_list):
    '''
    Get the metadata for a checksum, from the CVE database.
    :param db: the checksum db with metadata
    :param checksum: the checksum provided
    :param which_list: a string for the field name, like file_path
    '''
    if not db or checksum not in db:
        return ''
    entry = db[checksum]
    if which_list in entry:
        return entry[which_list]
    return ''


g_checksum_cache_db = {}
def create_hash_tree_for_checksum(checksum, ancestors, checksum_db, checksum_line):
    '''
    Create the hash tree for a checksum, based on the checksum database.
    This function recurses on itself.
    :param checksum: the checksum provided, which should be node_id of checksum_db
    :param ancestors: the list of checksums that are ancestors of this checksum
    :param checksum_db: the checksum database
    :param checksum_line: the checksum line from gitBOM doc for this checksum (node_id)
    returns a multi-tier dict with checksum nodes associated with metadata like CVElist/FixedCVElist
    '''
    # check the cache_db for performance benefit
    if checksum_line in g_checksum_cache_db:
        return g_checksum_cache_db[checksum_line]
    # check for recursion loop
    if checksum in ancestors:
        print("Error in creating hash tree: loop detected for checksum " + checksum + " ancestors: " + str(ancestors))
        return "RECURSION_LOOP_DETECTED"
    entry = {}
    if checksum in checksum_db:
        # Get a shallow copy which should keep metadata like file_path, etc., if it exists
        entry = checksum_db[checksum].copy()
    if "hash_tree" not in entry:  # leaf node
        for which_list in ("CVElist", "FixedCVElist"):
            cvelist = get_metadata_for_checksum_from_db(g_cvedb, checksum, which_list)
            if cvelist:
                entry[which_list] = cvelist
        if ("CVElist" in entry or "FixedCVElist" in entry) and "file_path" not in entry:
            file_path = get_metadata_for_checksum_from_db(g_cvedb, checksum, "file_path")
            if file_path:
                entry["file_path"] = file_path
        for which_list in ("file_path", "build_cmd"):
            if not g_metadata_db or which_list in entry:
                continue
            metadata = get_metadata_for_checksum_from_db(g_metadata_db, checksum, which_list)
            if metadata:
                entry[which_list] = metadata
        # the shallow copy of the checksum node is used, this should be fine
        g_checksum_cache_db[checksum_line] = entry
        return entry
    # non-leaf node, it has more lower level nodes
    hashes = entry["hash_tree"]
    ret = {}
    ancestors.append(checksum)  # add myself to the list of ancestors
    for ahash in set(hashes):
        # ahash is either checksum only or the checksum_line: blob sha1 bom sha1
        node_id = get_node_id_from_checksum_line(ahash)
        # recursion
        ret[ahash] = create_hash_tree_for_checksum(node_id, ancestors, checksum_db, ahash)
    # update metadata for this non-leaf node, based on blob_id
    blob_id, bom_id = get_blob_bom_id_from_checksum_line(checksum_line)
    for which_list in ("CVElist", "FixedCVElist"):
        cvelist = get_metadata_for_checksum_from_db(g_cvedb, blob_id, which_list)
        if cvelist:
            ret[which_list] = cvelist
    for key in ("file_path", "file_paths", "build_cmd"):  # try to save more metadata in the result
        if key in entry:
            ret[key] = entry[key]
    if ("CVElist" in ret or "FixedCVElist" in ret) and "file_path" not in ret:
        file_path = get_metadata_for_checksum_from_db(g_cvedb, blob_id, "file_path")
        if file_path:
            ret["file_path"] = file_path
    if g_metadata_db:
        for which_list in ("file_path", "build_cmd"):
            if which_list in ret:
                continue
            metadata = get_metadata_for_checksum_from_db(g_metadata_db, blob_id, which_list)
            if metadata:
                ret[which_list] = metadata
    # checksum_line contains both blob_id and bom_id, more accurate/representative than blob_id/bom_id alone
    g_checksum_cache_db[checksum_line] = ret
    ancestors.pop()  # remove myself from the list of ancestors
    return ret


def create_hash_tree_for_checksums(checksums, checksum_db):
    '''
    Create the hash tree for a list of checksums, based on the checksum database.
    :param checksums: the list of checksums provided
    :param checksum_db: the checksum database
    '''
    ret = {}
    for checksum in checksums:
        if checksum not in checksum_db:
            print("Warning: this checksum is not found in checksum DB: " + checksum)
            continue
        ancestors = []  # ancestors is used to detect/stop possible recursion loop
        tree = create_hash_tree_for_checksum(checksum, ancestors, checksum_db, checksum)
        ret[checksum] = tree
    return ret


def collect_cve_list_from_hash_tree(tree_db, which_list):
    '''
    Collect all the CVEs on a hash tree node.
    This function recurses on itself.
    :param tree_db: a node on the hash tree
    :param which_list: a string for the field name, CVEList or FixedCVElist
    '''
    if type(tree_db) is not dict:  # for "NOT_FOUND" or "RECURSION_LOOP_DETECTED"
        return []
    ret = []
    for checksum in tree_db:
        if checksum in ("file_path", "file_paths", "CVElist", "FixedCVElist"):
            #if checksum in ("file_path", "file_paths"):
            #    continue
            if checksum == which_list:
                ret.extend(tree_db[checksum])
            continue
        result = collect_cve_list_from_hash_tree(tree_db[checksum], which_list)
        ret.extend(result)
    return list(set(ret))


def find_cve_lists_for_checksums(checksums):
    '''
    find all the CVEs for a list of checksums.
    :param checksums: the list of checksums to find CVEs
    '''
    tree = create_hash_tree_for_checksums(checksums, g_checksum_db)
    if g_jsonfile and args.verbose > 1:
        save_json_db(g_jsonfile + "-details.json", tree)
    ret = {}
    for checksum in checksums:
        if checksum in tree:
            checksum_result = {}
            for which_list in ("CVElist", "FixedCVElist"):
                checksum_result[which_list] = collect_cve_list_from_hash_tree(tree[checksum], which_list)
            ret[checksum] = checksum_result
        else:
            ret[checksum] = "NOT_FOUND_IN_CHECKSUM_DB"
    return ret


def find_cve_lists_for_files(afiles):
    '''
    find all the CVEs for a list of binary files.
    :param afiles: the list of binary files to find CVEs
    '''
    file_checksums = {}
    checksums = []
    for afile in afiles:
        if os.path.exists(afile):
            checksum = get_git_file_hash(afile)
            checksums.append(checksum)
            file_checksums[afile] = checksum
        else:
            file_checksums[afile] = 'FILE_NOT_EXIST'
    result = find_cve_lists_for_checksums(checksums)
    for afile in file_checksums:
        checksum = file_checksums[afile]
        if checksum == 'FILE_NOT_EXIST':
            continue
        file_checksums[afile] = result[checksum]
    return file_checksums

############################################################
#### End of CVE handling routines ####
############################################################

def find_vulnerable_blob_ids_for_cve(cve, cve_db):
    '''
    Find all vulnerable git blob IDs for a CVE.
    :param cve_db: the CVE database from the bomsh_create_cve script.
    returns a list of vulnerable git blob IDs for a CVE.
    '''
    result = []
    for blob_id in cve_db:
        entry = cve_db[blob_id]
        if "CVElist" in entry:
            if cve in entry["CVElist"]:
                result.append(blob_id)
    return result


def find_vulnerable_blob_ids_for_cves(cves, cve_db):
    '''
    Find all vulnerable git blob IDs for a list of CVEs.
    :param cve_db: the CVE database from the bomsh_create_cve script.
    returns a list of vulnerable git blob IDs for each CVE.
    '''
    result = {}
    for cve in cves:
        blob_ids = find_vulnerable_blob_ids_for_cve(cve, cve_db)
        result[cve] = blob_ids
    return result


############################################################
#### End of CVE finding routines ####
############################################################


def rtd_parse_options():
    """
    Parse command options.
    """
    parser = argparse.ArgumentParser(
        description = "This tool searches CVE database and gitBOM database for binary files or CVEs")
    parser.add_argument("--version",
                    action = "version",
                    version=VERSION)
    parser.add_argument('-d', '--cve_db_file',
                    help = "the CVE database file, with git blob ID to CVE mappings")
    parser.add_argument('-r', '--raw_checksums_file',
                    help = "the raw checksum database file generated by bomsh_hook or bomsh_create_bom script")
    parser.add_argument('-b', '--bom_dir',
                    help = "the directory to store the generated gitBOM doc files")
    parser.add_argument('-e', '--cve_list_to_search',
                    help = "the comma-separated CVE list to search vulnerable git blob IDs")
    parser.add_argument('-c', '--checksums_to_search_cve',
                    help = "the comma-separated git blob ID or checksum list to search CVEs")
    parser.add_argument('-f', '--files_to_search_cve',
                    help = "the comma-separated files to search CVEs")
    parser.add_argument('-g', '--gitbom_ids_to_search_cve',
                    help = "the comma-separated gitBOM ID list to search CVEs")
    parser.add_argument('-m', '--metadata_db_file',
                    help = "the JSON database file containing metadata for file checksums")
    parser.add_argument('--tmpdir',
                    help = "tmp directory, which is /tmp by default")
    parser.add_argument('-j', '--jsonfile',
                    help = "the output JSON file for the search result")
    parser.add_argument("-v", "--verbose",
                    action = "count",
                    default = 0,
                    help = "verbose output, can be supplied multiple times"
                           " to increase verbosity")

    # Parse the command line arguments
    args = parser.parse_args()

    if not (args.cve_db_file and (args.raw_checksums_file or args.bom_dir)):
        print ("Please specify the CVE database file with -d option!")
        print ("Please specify the BOMSH raw checksum database file with -r option or the gitBOM directory with -b option!")
        print ("")
        parser.print_help()
        sys.exit()

    global g_jsonfile
    global g_tmpdir
    if args.tmpdir:
        g_tmpdir = args.tmpdir
        g_jsonfile = os.path.join(g_tmpdir, "bomsh_search_jsonfile")
    if args.jsonfile:
        g_jsonfile = args.jsonfile

    print ("Your command line is:")
    print (" ".join(sys.argv))
    print ("The current directory is: " + os.getcwd())
    print ("")
    return args


def main():
    global args
    # parse command line options first
    args = rtd_parse_options()

    global g_cvedb
    g_cvedb = load_json_db(args.cve_db_file)
    global g_metadata_db
    if args.metadata_db_file:
        g_metadata_db = load_json_db(args.metadata_db_file)
    elif args.bom_dir:
        bomsh_bomdir = os.path.join(args.bom_dir, "metadata", "bomsh")
        jsonfile = os.path.join(bomsh_bomdir, "bomsh_gitbom_treedb")
        if os.path.exists(jsonfile):
            g_metadata_db = load_json_db(jsonfile)
    global g_checksum_db
    if args.raw_checksums_file:
        g_checksum_db = load_json_db(args.raw_checksums_file)
    elif args.bom_dir:
        object_bomdir = os.path.join(args.bom_dir, "objects")
        if not os.path.exists(object_bomdir):
            print("Warning: gitBOM objects directory does not exist.")
            g_checksum_db = {}
        else:
            if args.files_to_search_cve:
                g_checksum_db = create_gitbom_doc_treedb_for_files(args.bom_dir, args.files_to_search_cve.split(","))
            else:
                g_checksum_db = create_gitbom_doc_treedb(object_bomdir)
    if args.verbose > 2:
        save_json_db(g_jsonfile + "-treedb.json", g_checksum_db)

    cve_result = {}
    if args.files_to_search_cve:
        afiles = args.files_to_search_cve.split(",")
        cve_result = find_cve_lists_for_files(afiles)
    elif args.checksums_to_search_cve:
        checksums = args.checksums_to_search_cve.split(",")
        cve_result = find_cve_lists_for_checksums(checksums)
    elif args.cve_list_to_search:
        cves = args.cve_list_to_search.split(",")
        cve_result = find_vulnerable_blob_ids_for_cves(cves, g_cvedb)
    elif args.gitbom_ids_to_search_cve:
        bom_ids = args.gitbom_ids_to_search_cve.split(",")
        cve_result = find_cve_lists_for_checksums(bom_ids)
    else:
        print("Did you forget providing files to search?")
        print("Try -c/-f/-g option.")
    if g_jsonfile:
        save_json_db(g_jsonfile, cve_result)
        if args.verbose > 2:
            save_json_db(g_jsonfile + "-cache.json", g_checksum_cache_db)
    print("\nHere is the CVE search results:")
    print(json.dumps(cve_result, indent=4, sort_keys=True))
    return


if __name__ == '__main__':
    main()
