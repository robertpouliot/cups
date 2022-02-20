#!/usr/bin/python
# Copyright: (c) 2019, Robert Pouliot <robert.pouliot@etisos.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: cups_printer

short_description: Create CUPS printer or class

version_added: "2.7"

description:
    - "Create a printer or printer class"
    - "This module requires the cups python module on every hosts."

options:
  printer:
    description:
       -  Is it a printer or a class
    default: true
    type: bool
  name: 
    description:
      - Name of the print queue
    required: true
  state:
    description:
      - Should we create of delete the printer
    default: present
    choices: [ present, absent ]
  info:
    description:
      - Information field of the printer, is not defined name of the queue
  location:
    description:
      - Where is the printer located
  ppd_type:
    description:
      - Type of PPD used. C(raw), raw print queues, C(cups) database of CUPS drivers,
        C(file) a local/remote PPD file, C(interface) script (CUPS <2.2.x and 
	    will always return changed)
    default: raw
    choices: [ raw, cups, file, interface ]
  ppd:
    description:
      - If C(ppd_type) is C(cups) use the PPD name in CUPS database.  If C(ppd_type) is  
        C(file) or C(interface) it's the filename used.
  remote_src:
    description:
      - Is the file on the master node or remote node. Only remote node supported for now.
    default: true
    type: bool
  device:
    description:
      - If C(type) is C(printer), the URI of the printer.
  members:
    description:
      - If C(type) is C(class), the list of print queues in class.
  enabled:
    description:
      - If printer/class is enabled to print.
    default: true
    type: bool
  accept:
    description:
      - If printer/class is accepting print job.
    default: true
    type: bool
  shared:
    description:
      - If printer/class is shared.
    default: true
    type: bool
  append:
    description:
      - If members of class are appended and not deleted.
    default: false
    type: bool
  op_policy:
    description:
      - Policy for print jobs.
  error_policy:
    description:
      - Policy when there is an error when printing.
  default:
    description:
      - If printer/class is default destination.
    default: false
    type: bool
  header:
    description:
      - Header banner page
  footer:
    description:
      - Header footer page


author:
    - Robert Pouliot (@rpouliot77)

requirements:
    - pycups
'''

EXAMPLES = '''
# Basic facts from local cups host
- name: Get CUPS facts
  cups_facts:

# Get facts from local CUPS host with different user
- name: Get CUPS fact with user cupsadm
  cups_facts:
    user: cupsadm
'''

RETURN = '''# '''

import os
#import pprint
from ansible.module_utils.basic import AnsibleModule

#pp = pprint.PrettyPrinter(indent=4)

try:
    import cups
    HAS_CUPS = True
except ImportError:
    HAS_CUPS = False

#CUPSPASS = ''
CupsConn = object
module = object


PRINTER_STATE = {
    3: 'Idle',
    4: 'Processing',
    5: 'Stopped'
}

#def cups_passwd():
#    """Callback for CUPS password"""
#    return CUPSPASS

def cups_remove_printer(nom):
    """Remove a printer from CUPS"""
    if module.check_mode:
        return True
    try:
        CupsConn.deletePrinter(nom)
        return True
    except cups.IPPError:
        module.fail_json(msg='Unable to delete printer')


def cups_create_printer(nom, device):
    """Create a new CUPS printer"""
    if module.check_mode:
        return True
    try:
        if module.params['printer']:
            if device is None:
                module.fail_json(msg='device required')
            if module.params['ppd_type'] == 'raw' or module.params['ppd_type'] is None:
                CupsConn.addPrinter(name=nom, device=device)
            elif module.params['ppd_type'] == 'cups':
                CupsConn.addPrinter(name=nom, device=device, ppdname=module.params['ppd'])
            else: # TODO: file or interface, only local for now
                CupsConn.addPrinter(name=nom, device=device, filename=module.params['ppd'])
        else:
            if module.params['members'] is None:
                module.fail_json(msg='members required')
            for item in module.params['members']:
                CupsConn.addPrinterToClass(item, nom)
        cups_param_func = [
            ['info', CupsConn.setPrinterInfo],
            ['location', CupsConn.setPrinterLocation],
            ['op_policy', CupsConn.setPrinterOpPolicy],
            ['error_policy', CupsConn.setPrinterErrorPolicy]
        ]
        for items in cups_param_func:
            if module.params[items[0]] is not None:
                items[1](nom, module.params[items[0]].decode('utf8'))
        # Voila le bout commun
        if module.params['default']:
            CupsConn.setDefault(nom)
        if module.params['shared'] or module.params['shared'] is None:
            CupsConn.setPrinterShared(nom, True)
        else:
            CupsConn.setPrinterShared(nom, False)
        if module.params['accept'] or module.params['accept'] is None:
            CupsConn.acceptJobs(nom)
        else:
            CupsConn.rejectJobs(nom)
        if module.params['enabled'] or module.params['enabled'] is None:
            CupsConn.enablePrinter(nom)
        else:
            CupsConn.disablePrinter(nom)
        if module.params['header'] is not None:
            header = module.params['header']
        else:
            header = 'none'
        if module.params['footer'] is not None:
            footer = module.params['footer']
        else:
            footer = 'none'
        CupsConn.setPrinterJobSheets(nom, header, footer)
    except cups.IPPError:
        module.fail_json(msg='Unable to create printer')
    return True

def cups_remake_printer_needed(nom, printer):
    """Verify if printer need to be deleted and recreated due to raw/PPD mismatch, return True if needed"""
    # Raw vs non-raw
    if module.params['ppd_type'] is None:
        return False
    if (printer["printer-make-and-model"].find('Local Raw Printer') != -1) != (module.params['ppd_type'] == 'raw'):
        return True
    if module.params['ppd_type'] == 'raw':
        return False
    pr_ppd = CupsConn.getPPD(nom)
    pr_sha = module.digest_from_file(pr_ppd, 'sha1')
    os.remove(pr_ppd)
    if module.params['ppd_type'] == 'file' or module.params['ppd_type'] == 'interface':
        # TODO: Remote file not supported yet
        if pr_sha == module.digest_from_file(module.params['ppd'], 'sha1'):
            return False
        else:
            return True
    # from cups DB
    try:
        cups_ppd = CupsConn.getServerPPD(module.params['ppd'])
        cups_sha = module.digest_from_file(cups_ppd, 'sha1')
        os.remove(cups_ppd)
        if cups_sha == pr_sha:
            return False
    except cups.IPPError:
        module.fail_json(msg='ppd does not exists')
    return True

def cups_modify_printer(nom, printers):
    """Modify CUPS printer"""
    printer = printers[nom]
    changed = False
    mp_remake = False

    try:
        def_printer = CupsConn.getDefault()
        printer.update(CupsConn.getPrinterAttributes(name=nom))
    except cups.IPPError:
        module.fail_json(msg='unable to modify printer/class')

    if printer["printer-make-and-model"].find('Local Printer Class') != -1:
        # class
        if module.params['printer']:
            module.fail_json(msg='name is a class and you want a printer')
    else:
        if not module.params['printer']:
            module.fail_json(msg='name is a printer and you want a class')

    # Check if we must recreate printer (not class) due to raw/ppd
    if module.params['printer']:
        if cups_remake_printer_needed(nom, printer):
            if module.check_mode:
                return True
            else:
                mp_remake = True
                cups_remove_printer(nom)
                if module.params['device'] is not None:
                    cups_create_printer(nom, module.params['device'])
                else:
                    cups_create_printer(nom, printer['device-uri'])
                changed = True

    print_class_arg = [
        ['info', 'printer-info', CupsConn.setPrinterInfo],
        ['location', 'printer-location', CupsConn.setPrinterLocation],
        ['op_policy', 'printer-op-policy', CupsConn.setPrinterOpPolicy],
        ['error_policy', 'printer-error-policy', CupsConn.setPrinterErrorPolicy]
    ]

    try:
    # Get Default printer if any
        if nom == def_printer:
            if not module.params['default']:
                if module.check_mode:
                    return True
                else:
                    CupsConn.setDefault('')
        elif module.params['default']:
            if module.check_mode:
                return True
            else:
                CupsConn.setDefault(nom)
                changed = True

        for item in print_class_arg:
            if mp_remake:
                item[2](nom, printer[item[1]])
            if module.params[item[0]] is not None:
                if not item[1] in printer or module.params[item[0]].decode('utf8') != printer[item[1]]:
                    changed = True
                    if not module.check_mode:
                        item[2](nom, module.params[item[0]].decode('utf8'))
        # Rebuild config from previous printer, we are not in check_mode for this if
        if mp_remake:
            CupsConn.setPrinterShared(nom, printer['printer-is-shared'])
            if printer['printer-is-accepting-jobs']:
                CupsConn.acceptJobs(nom)
            else:
                CupsConn.rejectJobs(nom)
            if printer['printer-state'] == cups.IPP_PRINTER_STOPPED:
                CupsConn.disablePrinter(nom)
            else:
                CupsConn.enablePrinter(nom)
            CupsConn.setPrinterJobSheets(nom, printer['job-sheets-default'][0], printer['job-sheets-default'][1])
        if module.params['shared'] is not None:
            if module.params['shared'] != printer['printer-is-shared']:
                changed = True
                if not module.check_mode:
                    CupsConn.setPrinterShared(nom, module.params['shared'])
        if module.params['accept'] is not None:
            if module.params['accept']:
                if not printer['printer-is-accepting-jobs']:
                    changed = True
                    if not module.check_mode:
                        CupsConn.acceptJobs(nom)
            else:
                if printer['printer-is-accepting-jobs']:
                    changed = True
                    if not module.check_mode:
                        CupsConn.rejectJobs(nom)
        if module.params['enabled'] is not None:
            if module.params['enabled']:
                if printer['printer-state'] == cups.IPP_PRINTER_STOPPED:
                    changed = True
                    if not module.check_mode:
                        CupsConn.enablePrinter(nom)
            else:
                if printer['printer-state'] != cups.IPP_PRINTER_STOPPED:
                    changed = True
                    if not module.check_mode:
                        CupsConn.disablePrinter(nom)

        h_changed = False
        if module.params['header'] is not None:
            header = module.params['header']
            if header != printer['job-sheets-default'][0]:
                h_changed = True
        else:
            header = printer['job-sheets-default'][0]
        if module.params['footer'] is not None:
            footer = module.params['footer']
            if footer != printer['job-sheets-default'][1]:
                h_changed = True
        else:
            footer = printer['job-sheets-default'][1]
        if h_changed:
            changed = True
            if not module.check_mode:
                CupsConn.setPrinterJobSheets(nom, header, footer)

        # Is it printer or class
        if module.params['printer']:
            if module.params['device'] is not None and printer['device-uri'] != module.params['device']:
                changed = True
                if not module.check_mode:
                    CupsConn.setPrinterDevice(nom, module.params['device'])
        elif module.params['members'] is not None: # class and member specified
            if (set(module.params['members']) ^ set(printer['member-names'])) != set():
                if module.params['append']:
                    if (set(module.params['members']) - set(printer['member-names'])) != set():
                        changed = True
                else:
                    changed = True
                if module.check_mode:
                    return changed
                for ajout in (set(module.params['members']) - set(printer['member-names'])):
                    CupsConn.addPrinterToClass(ajout, nom)
                if not module.params['append']:
                    for retrait in (set(printer['member-names']) - set(module.params['members'])):
                        CupsConn.deletePrinterFromClass(retrait, nom)
    except cups.IPPError:
        module.fail_json(msg='unable to modify printer/class')
    return changed


def main():
    """The starting point of the module"""
#    global CUPSPASS
    global module
    global CupsConn
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        name=dict(type='str', required=True),
        #user=dict(type='str', required=False),
        #password=dict(type='str', required=False),
        printer=dict(type='bool', required=False, default=True),
        device=dict(type='str', required=False),
        info=dict(type='str', required=False),
        location=dict(type='str', required=False),
        # default will be raw (thru cups_create_printer)
        ppd_type=dict(type='str', required=False,
                      choices=['raw', 'cups', 'file', 'interface']),
        ppd=dict(type='str', required=False),
        op_policy=dict(type='str', required=False),
        error_policy=dict(type='str', required=False),
        shared=dict(type='bool', required=False),
        enabled=dict(type='bool', required=False),
        accept=dict(type='bool', required=False),
        default=dict(type='bool', required=False, default=False),
        append=dict(type='bool', required=False, default=False),
        remote_src=dict(type='bool', required=False, default=False),
        state=dict(type='str', required=False, default='present', choices=['absent', 'present']),
        header=dict(type='str', required=False),
        footer=dict(type='str', required=False),
        members=dict(type='list', required=False)
    )
    module = AnsibleModule(
        argument_spec=module_args,
        mutually_exclusive=[['device', 'members']],
        supports_check_mode=True
    )

    # seed the result dict in the object
    # we primarily care about changed and state
    # change is if this module effectively modified the target
    # state will include any data that you want your module to pass back
    # for consumption, for example, in a subsequent task

    result_ret = dict(
        changed=False
    )
    # the AnsibleModule object will be our abstraction working with Ansible
    # this includes instantiation, a couple of common attr would be the
    # args/params passed to the execution, as well as if the module
    # supports check mode

    if not HAS_CUPS:
        module.fail_json(msg='The cups python module is required')

    # manipulate or modify the state as needed (this is going to be the
    # part where your module will do what it needs to do)
    try:
    #    cups.setPasswordCB(cups_passwd)
    #    if module.params['user']:
    #        cups.setUser(module.params['user'])
    #    if module.params['password']:
    #        CUPSPASS = module.params['password']
        # Connect to CUPS
        CupsConn = cups.Connection()

        # Get CUPS Printers
        printers = CupsConn.getPrinters()
        pname = module.params['name']

        # Remove printer if required, easy case
        if module.params['state'] == 'absent':
            if pname in printers:
                result_ret['changed'] = cups_remove_printer(pname)
            module.exit_json(**result_ret)

        if not pname in printers:
            result_ret['changed'] = cups_create_printer(pname, module.params['device'])
        else:
            result_ret['changed'] = cups_modify_printer(pname, printers)
        module.exit_json(**result_ret)
    except cups.IPPError:
        module.fail_json(msg='Error in cups_printer module', **result_ret)

    # in the event of a successful module execution, you will want to
    # simple AnsibleModule.exit_json(), passing the key/value results
    module.exit_json(**result_ret)



if __name__ == '__main__':
    main()
