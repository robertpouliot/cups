#!/usr/bin/python
# Copyright: (c) 2019-2022, Robert Pouliot <krynos42@gmail.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible.module_utils.basic import AnsibleModule

ANSIBLE_METADATA = {
    'metadata_version': '0.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: cups_info

short_description: Get info from CUPS printing system

version_added: "2.7"

description:
    - "Get info from CUPS printing system"
    - "This module requires the cups python module on every hosts."

options:
    user:
        description:
            - The username used to connect to CUPS module
        required: false

author:
    - Robert Pouliot (@robertpouliot)
'''

EXAMPLES = '''
# Basic info from local cups host
- name: Get CUPS info
  cups_info:

# Get info from local CUPS host with different user
- name: Get CUPS fact with user cupsadm
  cups_info:
    user: cupsadm
'''

RETURN = '''
default:
    description: List de the default printer
    type: string
printers:
    description: The printers with options and status 
    type: dict
devices:
    description: List of all devices
    type: dict
dests:
    description: List of all dests
    type: dict
ppds:
    description: List of all available PPDs
    type: dict
'''

try:
    import cups
    HAS_CUPS = True
except ImportError:
    HAS_CUPS = False

def run_module():
    printer_state = ['Unknown0', 'Unknown1', 'Unknown2',
                     'Idle', 'Processing', 'Stopped']

    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        user=dict(type='str', required=False, default='')
    )

    # seed the result dict in the object
    # we primarily care about changed and state
    # change is if this module effectively modified the target
    # state will include any data that you want your module to pass back
    # for consumption, for example, in a subsequent task
    result = dict(
        changed=False,
        printers=dict(),
        ppds=dict(),
        devices=dict(),
        default=str(),
        dests=dict()
    )

    # the AnsibleModule object will be our abstraction working with Ansible
    # this includes instantiation, a couple of common attr would be the
    # args/params passed to the execution, as well as if the module
    # supports check mode
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    if not HAS_CUPS:
        module.fail_json(msg='The cups python module is required')

    # manipulate or modify the state as needed (this is going to be the
    # part where your module will do what it needs to do)
    try:
        if module.params['user']:
            cups.setUser(module.params['user'])
        # Connect to CUPS
        conn = cups.Connection()
        # Get CUPS Printers
        printers = conn.getPrinters()
        print_arg = [
            ['status_message', 'printer-state-message'],
            ['location', 'printer-location'],
            ['info', 'printer-info'],
            ['type', 'printer-type'],
            ['shared', 'printer-is-shared'],
            ['uri', 'device-uri'],
            ['model', 'printer-make-and-model']
        ]
        print_attr_arg = [
            ['color', 'color-supported', False],
            ['duplex', 'sides-supported', ['one-sided']],
            ['media_default', 'media-default', ''],
            ['op_policy', 'printer-op-policy', 'default'],
            ['error_policy', 'printer-error-policy', 'stop-printer']
        ]
        # Fill the blanks for printers
        for printer in printers:
            result['printers'][printer] = dict()
            print_attr = conn.getPrinterAttributes(name=printer)
            result['printers'][printer]['status'] = \
                printer_state[printers[printer]["printer-state"]]
            result['printers'][printer]['raw'] = \
                bool(printers[printer]["printer-make-and-model"].find('Raw Printer') != -1)
            for items in print_arg:
                result['printers'][printer][items[0]] = \
                    printers[printer][items[1]]
            for items in print_attr_arg:
                if items[1] in print_attr:
                    result['printers'][printer][items[0]] = \
                        print_attr[items[1]]
                else:
                    result['printers'][printer][items[0]] = items[2]

        result['ppds'] = conn.getPPDs()
        result['devices'] = conn.getDevices()
        result['dests'] = conn.getDests()
        result['default'] = conn.getDefault()
    except cups.IPPError:
        module.fail_json(msg='Error in cups_info module', **result)

    # in the event of a successful module execution, you will want to
    # simple AnsibleModule.exit_json(), passing the key/value results
    module.exit_json(**result)

def main():
    run_module()

if __name__ == '__main__':
    main()
