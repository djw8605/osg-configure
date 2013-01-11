"""
Module to handle attributes related to the slurm jobmanager 
configuration
"""
import os
import re
import logging

from osg_configure.modules import utilities
from osg_configure.modules import configfile
from osg_configure.modules import validation
from osg_configure.modules.jobmanagerbase import JobManagerConfiguration

__all__ = ['SLURMConfiguration']


class SLURMConfiguration(JobManagerConfiguration):
  """Class to handle attributes related to SLURM job manager configuration"""

  # Using PBS emulation in SLURM to interface with globus gatekeeper so
  # config files being used will be the globus PBS config files
  SLURM_CONFIG_FILE = '/etc/grid-services/available/jobmanager-pbs-seg'
  GRAM_CONFIG_FILE = '/etc/globus/globus-pbs.conf'
   
  def __init__(self, *args, **kwargs):
    # pylint: disable-msg=W0142
    super(SLURMConfiguration, self).__init__(*args, **kwargs)
    self.log('SLURMConfiguration.__init__ started')
    # dictionary to hold information about options
    self.options = {'slurm_location' : 
                      configfile.Option(name = 'slurm_location',
                                        default_value = '/usr',
                                        mapping = 'OSG_PBS_LOCATION'),
                    'job_contact' : 
                      configfile.Option(name = 'job_contact',
                                        mapping = 'OSG_JOB_CONTACT'),
                    'util_contact' : 
                      configfile.Option(name = 'util_contact',
                                        mapping = 'OSG_UTIL_CONTACT'),
                    'log_directory' : 
                      configfile.Option(name = 'log_directory',
                                        required = configfile.Option.OPTIONAL,
                                        default_value = ''),
                    'accounting_log_directory' : 
                      configfile.Option(name = 'accounting_log_directory',
                                        required = configfile.Option.OPTIONAL,
                                        default_value = ''),
                    'accept_limited' : 
                      configfile.Option(name = 'accept_limited',
                                        required = configfile.Option.OPTIONAL,
                                        opt_type = bool,
                                        default_value = False)}
    self.config_section = "SLURM"
    self.__set_default = True
    self.log('SLURMConfiguration.__init__ completed')
      
  def parseConfiguration(self, configuration):
    """Try to get configuration information from ConfigParser or SafeConfigParser object given
    by configuration and write recognized settings to attributes dict
    """
    self.log('SLURMConfiguration.parseConfiguration started')    

    self.checkConfig(configuration)

    if not configuration.has_section(self.config_section):
      self.log('SLURM section not found in config file')
      self.log('SLURMConfiguration.parseConfiguration completed')    
      return
    
    if not self.setStatus(configuration):
      self.log('SLURMConfiguration.parseConfiguration completed')    
      return True

    
    self.getOptions(configuration, ignore_options = ['enabled'])

    # set OSG_JOB_MANAGER and OSG_JOB_MANAGER_HOME
    self.options['job_manager'] = configfile.Option(name = 'job_manager',
                                                    value = 'PBS',
                                                    mapping = 'OSG_JOB_MANAGER')
    self.options['home'] = configfile.Option(name = 'job_manager_home',
                                             value = self.options['slurm_location'].value,
                                             mapping = 'OSG_JOB_MANAGER_HOME')

    # used to see if we need to enable the default fork manager, if we don't 
    # find the managed fork service enabled, set the default manager to fork
    # needed since the managed fork section could be removed after managed fork
    # was enabled 
    if (configuration.has_section('Managed Fork') and
        configuration.has_option('Managed Fork', 'enabled') and
        configuration.getboolean('Managed Fork', 'enabled')):
      self.__set_default = False
      
    self.log('SLURMConfiguration.parseConfiguration completed')    

  
# pylint: disable-msg=W0613
  def checkAttributes(self, attributes):
    """Check attributes currently stored and make sure that they are consistent"""
    self.log('SLURMConfiguration.checkAttributes started')    

    attributes_ok = True

    if not self.enabled:
      self.log('SLURM not enabled, returning True')
      self.log('SLURMConfiguration.checkAttributes completed')    
      return attributes_ok
    
    if self.ignored:
      self.log('Ignored, returning True')
      self.log('SLURMConfiguration.checkAttributes completed')    
      return attributes_ok

    # make sure locations exist
    if not validation.valid_location(self.options['pbs_location'].value):
      attributes_ok = False
      self.log("Non-existent location given: %s" % 
                          (self.options['pbs_location'].value),
                option = 'slurm_location',
                section = self.config_section,
                level = logging.ERROR)
                           

    if not self.validContact(self.options['job_contact'].value, 
                             'pbs'):
      attributes_ok = False
      self.log("Invalid job contact: %s" % 
                         (self.options['job_contact'].value),
               option = 'job_contact',
               section = self.config_section,
               level = logging.ERROR)
      
    if not self.validContact(self.options['util_contact'].value, 
                             'pbs'):
      attributes_ok = False
      self.log("Invalid util contact: %s" % 
                        (self.options['util_contact'].value),
               option = 'util_contact',
               section = self.config_section,
               level = logging.ERROR)
            
    self.log('SLURMConfiguration.checkAttributes completed')    
    return attributes_ok 
  
  def configure(self, attributes):
    """Configure installation using attributes"""
    self.log('SLURMConfiguration.configure started')

    if not self.enabled:
      self.log('PBS not enabled, returning True')
      self.log('SLURMConfiguration.configure completed')    
      return True

    if self.ignored:
      self.log("%s configuration ignored" % self.config_section, 
               level = logging.WARNING)
      self.log('SLURMConfiguration.configure completed')    
      return True

    # The accept_limited argument was added for Steve Timm.  We are not adding
    # it to the default config.ini template because we do not think it is
    # useful to a wider audience.
    # See VDT RT ticket 7757 for more information.
    if self.options['accept_limited'].value:
      if not self.enable_accept_limited(SLURMConfiguration.SLURM_CONFIG_FILE):
        self.log('Error writing to ' + SLURMConfiguration.SLURM_CONFIG_FILE, 
                 level = logging.ERROR)
        self.log('SLURMConfiguration.configure completed')
        return False
    else:
      if not self.disable_accept_limited(SLURMConfiguration.SLURM_CONFIG_FILE):
        self.log('Error writing to ' + SLURMConfiguration.SLURM_CONFIG_FILE, 
                 level = logging.ERROR)
        self.log('SLURMConfiguration.configure completed')
        return False

    self.disable_seg('pbs', SLURMConfiguration.SLURM_CONFIG_FILE)      
#    if self.options['seg_enabled'].value:
#      self.enable_seg('pbs', SLURMConfiguration.SLURM_CONFIG_FILE)
#    else:
#      self.disable_seg('pbs', SLURMConfiguration.SLURM_CONFIG_FILE)
    
    if not self.setupGramConfig():
      self.log('Error writing to ' + SLURMConfiguration.GRAM_CONFIG_FILE,
               level = logging.ERROR)
      return False
    
    if self.__set_default:
      self.log('Configuring gatekeeper to use regular fork service')
      self.set_default_jobmanager('fork')

    self.log('SLURMConfiguration.configure completed')    
    return True
  
  def moduleName(self):
    """Return a string with the name of the module"""
    return "SLURM"
  
  def separatelyConfigurable(self):
    """Return a boolean that indicates whether this module can be configured separately"""
    return True
  
  def parseSections(self):
    """Returns the sections from the configuration file that this module handles"""
    return [self.config_section]

  def setupGramConfig(self):
    """
    Populate the gram config file with correct values
    
    Returns True if successful, False otherwise
    """    
    contents = open(SLURMConfiguration.GRAM_CONFIG_FILE).read()
    bin_location = os.path.join(self.options['pbs_location'].value,
                                'bin',
                                'qsub')
    if validation.valid_file(bin_location):
      re_obj = re.compile('^qsub=.*$', re.MULTILINE)
      (contents, count) = re_obj.subn("qsub=\"%s\"" % bin_location,
                                    contents,
                                    1)
      if count == 0:
        contents += "qsub=\"%s\"\n" % bin_location
    bin_location = os.path.join(self.options['pbs_location'].value,
                                'bin',
                                'qstat')
    if validation.valid_file(bin_location):
      re_obj = re.compile('^qstat=.*$', re.MULTILINE)
      (contents, count) = re_obj.subn("qstat=\"%s\"" % bin_location, contents, 1)
      if count == 0:
        contents += "qstat=\"%s\"\n" % bin_location
    bin_location = os.path.join(self.options['pbs_location'].value,
                                'bin',
                                'qdel')
    if validation.valid_file(bin_location):
      re_obj = re.compile('^qdel=.*$', re.MULTILINE)
      (contents, count) = re_obj.subn("qdel=\"%s\"" % bin_location,
                                    contents,
                                    1)
      if count == 0:
        contents += "qdel=\"%s\"\n" % bin_location
        
    if self.options['seg_enabled'].value:
      if (self.options['log_directory'].value is None or
          not validation.valid_directory(self.options['log_directory'].value)):
        mesg = "%s is not a valid directory location " % self.options['log_directory'].value
        mesg += "for pbs log files"
        self.log(mesg, 
                 section = self.config_section,
                 option = 'log_directory',
                 level = logging.ERROR)
        return False

      new_setting = "log_path=\"%s\"" % self.options['log_directory'].value
      re_obj = re.compile('^log_path=.*$', re.MULTILINE)
      (contents, count) = re_obj.subn(new_setting, contents, 1)
      if count == 0:
        contents += new_setting + "\n"

    if not utilities.atomic_write(SLURMConfiguration.GRAM_CONFIG_FILE, contents):
      return False
    
    return True
      
         
      