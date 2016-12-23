#   Copyright 2016 Huawei, Inc. All rights reserved.
#
#   Licensed under the Apache License, Version 2.0 (the "License"); you may
#   not use this file except in compliance with the License. You may obtain
#   a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#   WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#   License for the specific language governing permissions and limitations
#   under the License.
#


"""Nimble v1 Baremetal server action implementations"""

import logging

from osc_lib.cli import parseractions
from osc_lib.command import command
from osc_lib import exceptions
from osc_lib import utils
import six

from nimbleclient.common.i18n import _

LOG = logging.getLogger(__name__)


class CreateServer(command.ShowOne):
    """Create a new baremetal server"""

    def get_parser(self, prog_name):
        parser = super(CreateServer, self).get_parser(prog_name)
        parser.add_argument(
            "name",
            metavar="<name>",
            help=_("New baremetal server name")
        )
        parser.add_argument(
            "--flavor",
            metavar="<flavor>",
            required=True,
            help=_("ID or Name of baremetal server flavor"),
        )
        parser.add_argument(
            "--image",
            metavar="<image>",
            required=True,
            help=_("ID or Name of image"),
        )
        parser.add_argument(
            "--nic",
            metavar="uuid=NETWORK[,port-type=PORT_TYPE]",
            required_keys=['uuid'],
            optional_keys=['port-type'],
            action=parseractions.MultiKeyValueAction,
            help=_("Create a NIC on the server. "
                   "(repeat option to create multiple NICs)"),
        )
        parser.add_argument(
            "--description",
            metavar="<description>",
            help=_("Baremetal server description"),
        )
        parser.add_argument(
            "--availability-zone",
            metavar="<zone-name>",
            help=_("The availability zone for the baremetal server placement"),
        )
        parser.add_argument(
            "--extra",
            metavar="<extra>",
            help=_("The extra information for baremetal server"),
        )
        return parser

    def take_action(self, parsed_args):
        bc_client = self.app.client_manager.baremetal_compute
        flavor_data = utils.find_resource(
            bc_client.flavor,
            parsed_args.flavor)
        image_data = utils.find_resource(
            self.app.client_manager.image.images,
            parsed_args.image)

        data = bc_client.server.create(
            name=parsed_args.name,
            image_uuid=image_data.id,
            flavor_uuid=flavor_data.uuid,
            description=parsed_args.description,
            networks=parsed_args.nic,
            availability_zone=parsed_args.availability_zone,
            extra=parsed_args.extra
        )
        info = {}
        info.update(data._info)
        return zip(*sorted(six.iteritems(info)))


class DeleteServer(command.Command):
    """Delete existing baremetal erver(s)"""

    def get_parser(self, prog_name):
        parser = super(DeleteServer, self).get_parser(prog_name)
        parser.add_argument(
            'server',
            metavar='<server>',
            nargs='+',
            help=_("Baremetal server(s) to delete (name or UUID)")
        )
        return parser

    def take_action(self, parsed_args):
        bc_client = self.app.client_manager.baremetal_compute
        result = 0
        for one_server in parsed_args.server:
            try:
                data = utils.find_resource(
                    bc_client.server, one_server)
                bc_client.server.delete(data.uuid)
            except Exception as e:
                result += 1
                LOG.error(_("Failed to delete server with name or UUID "
                            "'%(server)s': %(e)s") %
                          {'server': one_server, 'e': e})

        if result > 0:
            total = len(parsed_args.server)
            msg = (_("%(result)s of %(total)s baremetal servers failed "
                     "to delete.") % {'result': result, 'total': total})
            raise exceptions.CommandError(msg)


class ListServer(command.Lister):
    """List all baremetal servers"""

    def get_parser(self, prog_name):
        parser = super(ListServer, self).get_parser(prog_name)
        parser.add_argument(
            '--detailed',
            action='store_true',
            default=False,
            help=_("List additional with details.")
        )
        return parser

    @staticmethod
    def _networks_formatter(network_info):
        return_info = []
        for port_uuid in network_info:
            port_ips = []
            for fixed_ip in network_info[port_uuid]['fixed_ips']:
                port_ips.append(fixed_ip['ip_address'])
            return_info.append(', '.join(port_ips))
        return '; '.join(return_info)

    def take_action(self, parsed_args):
        bc_client = self.app.client_manager.baremetal_compute

        if parsed_args.detailed:
            data = bc_client.server.list(detailed=True)
            formatters = {'network_info': self._networks_formatter}
            # This is the easiest way to change column headers
            column_headers = (
                "UUID",
                "Name",
                "Flavor",
                "Status",
                "Image",
                "Description",
                "Availability Zone",
                "Networks"
            )
            columns = (
                "uuid",
                "name",
                "instance_type_uuid",
                "status",
                "image_uuid",
                "description",
                "availability_zone",
                "network_info"
            )
        else:
            data = bc_client.server.list()
            formatters = None
            column_headers = (
                "UUID",
                "Name",
                "Status",
            )
            columns = (
                "uuid",
                "name",
                "status",
            )

        return (column_headers,
                (utils.get_item_properties(
                    s, columns, formatters=formatters
                ) for s in data))


class ShowServer(command.ShowOne):
    """Display baremetal server details"""

    def get_parser(self, prog_name):
        parser = super(ShowServer, self).get_parser(prog_name)
        parser.add_argument(
            'server',
            metavar='<server>',
            help=_("Baremetal server to display (name or UUID)")
        )
        return parser

    def take_action(self, parsed_args):
        bc_client = self.app.client_manager.baremetal_compute
        data = utils.find_resource(
            bc_client.server,
            parsed_args.server,
        )

        info = {}
        info.update(data._info)
        return zip(*sorted(six.iteritems(info)))


class UpdateServer(command.ShowOne):
    """Update a baremetal server"""

    @staticmethod
    def _partition_kv(kv_arg):
        if ':' not in kv_arg:
            msg = _("Input %s should be a pair of key/value combined "
                    "by ':'")
            raise exceptions.CommandError(msg)
        kv = kv_arg.partition(":")
        return kv[0], kv[2]

    def get_parser(self, prog_name):
        parser = super(UpdateServer, self).get_parser(prog_name)
        parser.add_argument(
            'server',
            metavar='<server>',
            help=_("Baremetal server to update (name or UUID)")
        )
        parser.add_argument(
            "--description",
            metavar="<description>",
            help=_("Baremetal Server description"),
        )
        parser.add_argument(
            "--name",
            metavar="<description>",
            help=_("Baremetal server description"),
        )
        parser.add_argument(
            "--add-extra",
            action="append",
            type=self._partition_kv,
            metavar="<EXTRA_KEY:EXTRA_VALUE>",
            help="A pair of key:value to be added to the extra "
                 "field of the server.")
        parser.add_argument(
            "--replace-extra",
            action="append",
            type=self._partition_kv,
            metavar="<EXTRA_KEY:EXTRA_VALUE>",
            help="A pair of key:value to be update to the extra "
                 "field of the serve.")
        parser.add_argument(
            "--remove-extra",
            action="append",
            metavar="<EXTRA_KEY>",
            help="Delete an item of the field of the server with the key "
                 "specified.")
        return parser

    def take_action(self, parsed_args):

        bc_client = self.app.client_manager.baremetal_compute
        server = utils.find_resource(
            bc_client.server,
            parsed_args.server,
        )
        updates = []
        if parsed_args.description:
            updates.append({"op": "replace",
                            "path": "/description",
                            "value": parsed_args.description})
        if parsed_args.name:
            updates.append({"op": "replace",
                            "path": "/name",
                            "value": parsed_args.name})
        for key, value in parsed_args.add_extra or []:
            updates.append({"op": "add",
                            "path": "/extra/%s" % key,
                            "value": value})

        for key, value in parsed_args.replace_extra or []:
            updates.append({"op": "replace",
                            "path": "/extra/%s" % key,
                            "value": value})
        for key in parsed_args.remove_extra or []:
            updates.append({"op": "remove",
                            "path": "/extra/%s" % key})
        data = bc_client.server.update(server_id=server.uuid,
                                       updates=updates)
        info = {}
        info.update(data._info)
        return zip(*sorted(six.iteritems(info)))


class SetServerPowerState(command.Command):
    """Set the power state of baremetal server"""

    def get_parser(self, prog_name):
        parser = super(SetServerPowerState, self).get_parser(prog_name)
        parser.add_argument(
            'server',
            metavar='<server>',
            help=_("Baremetal server to update (name or UUID)")
        )
        parser.add_argument(
            "--power-state",
            metavar="<power-state>",
            choices=['on', 'off', 'reboot'],
            required=True,
            help=_("Power state to be set to the baremetal server, must be "
                   "one of: 'on', 'off' and 'reboot'.")
        )
        return parser

    def take_action(self, parsed_args):
        bc_client = self.app.client_manager.baremetal_compute
        server = utils.find_resource(
            bc_client.server,
            parsed_args.server,
        )
        bc_client.server.set_power_state(server_id=server.uuid,
                                         power_state=parsed_args.power_state)
