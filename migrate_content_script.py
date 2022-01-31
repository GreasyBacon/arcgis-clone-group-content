import logging
import argparse
import uuid
import os, sys
from arcgis.gis import GIS

logger = logging.getLogger(os.path.splitext(os.path.basename(sys.argv[0]))[0])


def parse_args(args=sys.argv[1:]):
	""""""
	ap = argparse.ArgumentParser()
	ap.add_argument("-spurl", "--sourceportal_url", metavar="URL", required=True, help="The URL of the source portal.")
	ap.add_argument("-spun", "--sourceportal_username", metavar="USERNAME", required=True, help="The username of the account accessing the source portal.")
	ap.add_argument("-sppw", "--sourceportal_password", metavar="PASSWORD", required=True, help="The password of the account accessing the source portal.")
	ap.add_argument("-spgrp", "--sourceportal_group", metavar="GROUP_NAME", required=True, help="The group in the source portal used to export an EPK file.")
	ap.add_argument("-tpurl", "--targetportal_url", metavar="URL", required=True, help="The URL of the target portal.")
	ap.add_argument("-tpun", "--targetportal_username", metavar="USERNAME", required=True, help="The username of the account accessing the target portal.")
	ap.add_argument("-tppw", "--targetportal_password", metavar="PASSWORD", required=True, help="The password of the account accessing the target portal.")
	ap.add_argument("-tpgrp", "--targetportal_group", metavar="GROUP_NAME", required=False, help="The group in the target portal that the imported EPK items will be shared to.")
	return ap.parse_args(args)


def setup_logging():
	"""Configure logging."""
	root = logging.getLogger("")
	root.setLevel(logging.INFO)
	logger.setLevel(logging.INFO)
	ch = logging.StreamHandler()
	ch.setFormatter(logging.Formatter("%(levelname)s[%(name)s] %(message)s"))
	root.addHandler(ch)


def get_portal(url, username, password):
	"""Given a URL and crentials, return a GIS object representing a Portal for ArcGIS connection."""
	portal = GIS(url, username, password, verify_cert=False)
	logging.info("Successfully connected to: {}".format(portal.url))
	return portal


def get_group(portal, name=None, action="search"):
	"""Given a portal, either search for or create a group within said portal. Name is optional if creating a group."""
	if action == "search":
		groups = portal.groups.search(name)
		group = groups[0]
		logging.info("Found group {}.".format(group.title))
		return group
	elif action == "create":
		if not name:
			unique_id = str(uuid.uuid4()).split('-')[0]
			name = "MigrationGroup_{}".format(unique_id)
		group = portal.groups.create(title=name, tags=default_tags)
		logging.info("Created group {}.".format(name))
		return group


def create_epk_file(group):
	"""Given a group in a portal, create an EPK file (export package) which will then be downloaded to a default path location."""
	epk_item = source_group.migration.create(future=False)
	
	# if successful, epk_item will be an "Item", if unsuccessful, epk_item will be a "Dict" that contains a 'result' key
	if epk_item.get('result', None):
		logging.info("EPK item creation unsuccessful.")
		logging.info("EPK item creation results: {}.".format(epk_item))
		raise Exception("EPK Item could not be created successfully.")
	
	logging.info("Attempting to download EPK item: {}".format(epk_item.title))
	epk_file = epk_item.download()
	return epk_file


def upload_epk_file(portal, file, name=None):
	"""Given a portal and a filepath, upload an EPK file to the portal. Name for the file in portal is optional."""
	unique_id = str(uuid.uuid4()).split('-')[0]
	up_epk_item_name = name or 'EPK_Migration_Item_{}'.format(unique_id)
	up_epk_item = portal.content.add({'title':up_epk_item_name, 
    		                         'tags':default_tags, 
            	                     'type':"Export Package"}, 
                	                 data=file)
	logging.info("EPK Item {} uploaded to Portal {}.".format(up_epk_item_name, portal.url))
	return up_epk_item


if __name__ == "__main__":

	options = parse_args()
	setup_logging()
	default_tags = ["EPK_Import"]

	try:
		logging.info("Connecting to source portal.")
		source_portal = get_portal(options.sourceportal_url, options.sourceportal_username, options.sourceportal_password)
		
		logging.info("Finding group {} in source portal.".format(options.sourceportal_group))
		source_group = get_group(source_portal, options.sourceportal_group, action="search")

		logging.info("Creating EPK file for group {}.".format(options.sourceportal_group))
		source_epk_file = create_epk_file(source_group)

		logging.info("EPK file - {} - downloaded.".format(source_epk_file))

		logging.info("Connecting to target portal.")
		target_portal = get_portal(options.targetportal_url, options.targetportal_username, options.targetportal_password)
		
		# "--targetportal_group" is an optional parameter, as we can create a group on the fly in the target portal if one does not exist
		if options.targetportal_group:
			logging.info("Finding group {} in target portal.".format(options.targetportal_group))
			target_group = get_group(target_portal, options.targetportal_group, action="search")  
		else:
			logging.info("No group name for target portal provided. Creating new group.")
			target_group = get_group(target_portal, None, action="create")

		logging.info("Uploading EPK item to target portal.")
		up_epk_item = upload_epk_file(target_portal, source_epk_file, None)
		
		logging.info("Sharing uploaded EPK file in target portal with group {}.".format(target_group.title))
		up_epk_item.share(groups=[target_group])

		logging.info("Creating migration for EPK item uploaded in target portal.")
		target_migrator = target_group.migration

		logging.info("Inspecting migration for EPK item.")
		resp = target_migrator.inspect(up_epk_item)
		logging.info("Inspection results: {}".format(resp))

		logging.info("Creating cloned content in target portal.")
		grpMigrateResult = target_migrator.load(up_epk_item, future=False)  

		logging.info("Result of cloning content: {}".format(grpMigrateResult))
		logging.info("All done, clocking off for an alcoholic or non-alcoholic beverage now!")

	except Exception as e:
		logger.exception("%s", e)
		sys.exit(1)
	sys.exit(0)