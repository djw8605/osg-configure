#!/usr/bin/python

""" Module to hold various utility functions """

import re, socket, os, types, pwd, sys, glob, ConfigParser
import tempfile, subprocess

from osg_configure.modules import exceptions
from osg_configure.modules import validation

__all__ = ['using_prima',
           'using_xacml_protocol',
           'get_vos',
           'enable_service',
           'disable_service',
           'service_enabled',    
           'get_elements',
           'get_hostname',
           'get_set_membership',
           'blank',
           'get_gums_host',
           'create_map_file',
           'fetch_crl',
           'ce_config']
  
CONFIG_DIRECTORY = "/etc/osg"

  
def using_prima():
  """
  Function to check whether prima callouts are setup
  """
  
  if (not validation.valid_file('/etc/grid-security/gsi-authz.conf') or
      not validation.valid_file('/etc/grid-security/prima-authz.conf')):
    return False
    
  gsi_set = False
  prima_set = False
  gsi_buffer = open('/etc/grid-security/gsi-authz.conf').read()
  prima_buffer = open('/etc/grid-security/prima-authz.conf').read()

  if re.search('^\s*globus_mapping', gsi_buffer, re.M):
    gsi_set = True

  if re.search('^\s*imsContact https://(.*?):\d+', prima_buffer, re.M):
    prima_set = True

  if gsi_set and prima_set:
    return True
  
  return False

def using_xacml_protocol():
  """
  Function to check to see whether the system is using xacml to talk to GUMS
  """
  
  if not using_prima():
    return False
  
  gsi_buffer = open('/etc/grid-security/gsi-authz.conf').read(8192)

  if re.search('^globus_mapping.*_scas_.*', gsi_buffer, re.M):
    return True
  
  return False
  
def get_gums_host():
  """
  Function to return the gums host being used on the system, returns a tuple 
  with the host name and port of the gums host or None if a gums host is not being used
  """

  if 'VDT_GUMS_HOST' in os.environ:
    return (os.environ['VDT_GUMS_HOST'], 8443)
  
  if not using_prima():
    return None
    
  prima_buffer = open('/etc/grid-security/prima-authz.conf').read(8192)

  match = re.search('^\s*imsContact https://(.*?):(\d+)?', prima_buffer, re.M)      
  if match:
    host = match.group(1)
    port = match.group(2)
    return (host, port)
  
  return None
      
def get_elements(element=None, filename=None):
  """Get values for selected element from xml file specified in filename"""
  if filename is None or element is None:
    return []
  import xml.dom.minidom
  try:
    dom = xml.dom.minidom.parse(filename)
  except IOError:
    return []
  except xml.parsers.expat.ExpatError:
    return []
  values = dom.getElementsByTagName(element)
  return values
    
def write_attribute_file(filename=None, attributes=None):
  """
  Write attributes to osg attributes file in an atomic fashion
  """
  
  if attributes is None or filename is None:
    attributes = {}
  base_dir = os.path.dirname(filename)
  (fd, tmp_name) = tempfile.mkstemp(text=True, dir=base_dir)
  file_handle = os.fdopen(fd, 'w')
  variable_string = ""
  export_string = ""
  # keep a list of array variables 
  array_vars = {}
  keys = attributes.keys()
  keys.sort()
  for key in keys:
    if type(attributes[key]) is types.ListType:
      for item in attributes[key]:
        variable_string += "%s=\"%s\"\n" % (key, item)
    else:  
      variable_string += "%s=\"%s\"\n" % (key, attributes[key])
    if len(key.split('[')) > 1:
      real_key = key.split('[')[0]
      if real_key not in array_vars:
        export_string += "export %s\n" % key.split('[')[0]
        array_vars[real_key] = ""
    else:
      export_string += "export %s\n" % key
       
  file_handle.write("#!/bin/sh\n")
  file_handle.write("#---------- This file automatically generated by " \
                    "configure-osg \n")
  file_handle.write("#---------- This is periodically overwritten.  " \
                    "DO NOT HAND EDIT\n")
  file_handle.write("#---------- Instead, write any environment variable " \
                    "customizations into\n")
  file_handle.write("#---------- the config.ini [Local Settings] section, " \
                    "as documented here:\n")
  file_handle.write("#---------- https://twiki.grid.iu.edu/bin/view/Release"\
                    "Documentation/ConfigurationFileLocalSettings\n")
  file_handle.write("#---  variables -----\n")
  file_handle.write(variable_string)
  file_handle.write("#--- export variables -----\n")
  file_handle.write(export_string)
  file_handle.close()
  os.rename(tmp_name, filename)
  os.chmod(filename, 0644)
  return True

def get_set_membership(test_set, reference_set, defaults = None):
  """
  See if test_set has any elements that aren't keys of the reference_set 
  or optionally defaults.  Takes lists as arguments
  """
  missing_members = []
  
  if defaults is None:
    defaults = []
  for member in test_set:
    if member not in reference_set and member not in defaults:
      missing_members.append(member)
  return missing_members

def get_hostname():
  """Returns the hostname of the current system"""
  try:
    return socket.gethostbyaddr(socket.gethostname())[0]
  # pylint: disable-msg=W0703
  except Exception:
    return None
  return None

def blank(value):
  """Check the value to check to see if it is 'UNAVAILABLE' or blank, return True 
  if that's the case
  """
  if type(value) != types.StringType:
    if value is None:
      return True
    return False
  
  if (value.upper().startswith('UNAVAILABLE') or
      value == "" or
      value is None):
    return True
  return False

def get_vos(user_vo_file):
  """
  Returns a list of valid VO names.
  """

  if (user_vo_file is None or 
      not os.path.isfile(user_vo_file)):
    user_vo_file = os.path.join(os.path.join(CONFIG_DIRECTORY, 
                                             'osg-user-vo-map.txt'))
  if not os.path.isfile(user_vo_file):
    return []
  file_buffer = open(os.path.expandvars(user_vo_file), 'r')
  vo_list = []
  for line in file_buffer:
    try:
      line = line.strip()
      if line.startswith("#"):
        continue
      vo = line.split()[1]
      if vo.startswith('us'):
        vo = vo[2:]
      if vo not in vo_list:
        vo_list.append(vo)
    except (KeyboardInterrupt, SystemExit):
      raise
    except:
      pass
  return vo_list

def service_enabled(service_name):
  """
  Check to see if a service is enabled
  """
  if service_name == None or service_name == "":
    return False
  process = subprocess.Popen(['/sbin/service', '--list', service_name], 
                             stdout=subprocess.PIPE)
  output = process.communicate()[0]
  if process.returncode != 0:
    return False  

  match = re.search(service_name + '\s*\|.*\|\s*([a-z ]*)$', output)
  if match:
    # The regex above captures trailing whitespace, so remove it
    # before we make the comparison. -Scot Kronenfeld 2010-10-08
    if match.group(1).strip() == 'enable':
      return True
    else:
      return False
  else:
    return False 
  
def create_map_file(using_gums = False):
  """
  Check and create a mapfile if needed
  """

  map_file = os.path.join(CONFIG_DIRECTORY,
                          'osg-user-vo-map.txt')
  result = True
  try:
    if validation.valid_user_vo_file(map_file):
      return result
    if using_gums:
      gums_script = os.path.join('usr',
                                 'bin',
                                 'gums-host-cron')
    else:
      gums_script = os.path.join('usr'
                                 'bin',
                                 'edg-mkgridmap')
      
    sys.stdout.write("Running %s, this process may take some time " % gums_script +
                     "to query vo and gums servers\n")
    sys.stdout.flush()
    if not run_script([gums_script]):
      return False    
  except IOError:
    result = False
  return result

def fetch_crl():
  """
  Run fetch_crl script and return a boolean indicating whether it was successful
  """

  try:
    if 'X509_CADIR' not in os.environ:
      sys.stdout.write("Can't find CA directory, assuming crl files not present\n")
    else:
      crl_files = glob.glob(os.path.join(os.environ['X509_CADIR'], '*.r0'))
      if len(crl_files) > 0:
        sys.stdout.write("CRLs exist, skipping fetch-crl invocation\n")
        sys.stdout.flush()
        return True
      
    crl_path = os.path.join('usr',
                            'bin',
                            'fetch-crl.cron')
                 
    if len(glob.glob(crl_path)) > 0:
      crl_script = glob.glob(crl_path)[0]
    
    sys.stdout.write("Running %s, this process make take " % crl_script +
                     "some time to fetch all the crl updates\n")
    sys.stdout.flush()
    if not run_script([crl_script]):
      return False
  except IOError:
    return False
  return True

def run_script(script):
  """
  Arguments:
  script - a string or a list of arguments to run formatted while 
           the args argument to subprocess.Popen
  
  Returns:
  True if script runs successfully, False otherwise
  """
  
  if not validation.valid_executable(script[0]):
    return False

  process = subprocess.Popen(script)
  process.communicate()
  if process.returncode != 0:
    return False
    
  return True          


def get_condor_location(default_location = '/usr'):
  """
  Check environment variables to try to get condor location preferring 
  VDTSET_CONDOR_LOCATION over CONDOR_LOCATION
  """

  if 'CONDOR_LOCATION' in os.environ:
    return os.path.normpath(os.environ['CONDOR_LOCATION'])  
  elif not blank(default_location):
    return default_location
  else:
    return ""

def get_condor_config(default_config = '/etc/condor'):
  """
  Check environment variables to try to get condor config preferring 
  VDTSET_CONDOR_CONFIG over CONDOR_CONFIG
  """
  
  if 'CONDOR_CONFIG' in os.environ:
    return os.path.normpath(os.environ['CONDOR_CONFIG'])
  elif not blank(default_config):
    return os.path.normpath(default_config)
  else:
    return os.path.join(get_condor_location(),
                        'etc',
                        'condor_config')
