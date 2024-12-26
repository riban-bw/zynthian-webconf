# -*- coding: utf-8 -*-
# ********************************************************************
# ZYNTHIAN PROJECT: Zynthian Web Configurator
#
# Audio Configuration Handler
#
# Copyright (C) 2017-2024 Fernando Moyano <jofemodo@zynthian.org>
#
# ********************************************************************
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of
# the License, or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# For a full copy of the GNU General Public License see the LICENSE.txt file.
#
# ********************************************************************

import os
import logging
import tornado.web
from subprocess import check_output

from lib.zynthian_config_handler import ZynthianConfigHandler
import zynconf

# ------------------------------------------------------------------------------
# GIT Repository Configuration
# ------------------------------------------------------------------------------


class RepositoryHandler(ZynthianConfigHandler):
    zynthian_base_dir = os.environ.get('ZYNTHIAN_DIR', "/zynthian")
    stable_branch = os.environ.get('ZYNTHIAN_STABLE_BRANCH', "oram")
    stable_tag = os.environ.get('ZYNTHIAN_STABLE_TAG', "oram-2409")
    testing_branch = os.environ.get('ZYNTHIAN_TESTING_BRANCH', "vangelis")

    advanced_repository_list = [
        'zyncoder',
        'zynthian-sys',
        'zynthian-data'
    ]

    @tornado.web.authenticated
    def get(self, errors=None):
        super().get("Software Versions", self.get_config_info(), errors)

    @tornado.web.authenticated
    def post(self):
        postedConfig = tornado.escape.recursive_unicode(self.request.arguments)
        logging.info(postedConfig)
        try:
            version = postedConfig['ZYNTHIAN_VERSION'][0]
        except:
            version = self.stable_tag
        errors = {}
        changed_repos = 0
        for repo in zynconf.zynthian_repositories:
            posted_key = f"ZYNTHIAN_REPO_{repo}"
            if version == "custom":
                try:
                    branch = postedConfig[posted_key][0]
                except:
                    branch = None
            else:
                branch = version
            try:
                if branch and self.set_repo_branch(repo, branch):
                    changed_repos += 1
            except Exception as err:
                logging.error(err)
                errors[posted_key] = err

        config = self.get_config_info(version, postedConfig["_command"] != ["SAVE"])
        if changed_repos > 0:
            config['ZYNTHIAN_MESSAGE'] = {
                'type': 'html',
                'content': "<div class='alert alert-success'>Some repo changed its branch. You may want to <a href='/sw-update'>update the software</a> for getting the latest changes.</div>"
            }
            #self.restart_ui_flag = True
            #self.restart_webconf_flag = True

        super().get("Software Versions", config, errors)

    def get_config_info(self, version=None, refresh_repos=False):
        """
        Populates config with stable, staging and testing versions of each repository.
        If repository versions differ, custom is enabled.
        Custom option provides all tags and branches of each repository.
        """
        repo_branches = []
        if version is None or version == "custom":
            for repo in zynconf.zynthian_repositories:
                path = f"/zynthian/{repo}"
                branch = zynconf.get_git_tag(path)
                if branch is None:
                    branch = zynconf.get_git_branch(path)
                repo_branches.append(branch)
                if branch != repo_branches[0]:
                    version = "custom"
        if repo_branches and version != "custom":
            version = repo_branches[0]

        version_options = {}
        version_options[self.stable_tag] = f"Stable ({self.stable_tag}) - Current stable release version"
        version_options[self.stable_branch] = f"Staging ({self.stable_branch}) - Pre-release testing version"
        version_options[self.testing_branch] = f"Testing ({self.testing_branch}) - Active development version"
        version_options["custom"] = "Custom - User selected versions of each repository (allow 10s after selecting for webpage to refresh)"

        config = {
            "ZYNTHIAN_VERSION": {
                'type': 'select',
                'title': 'Version',
                        'value': version,
                        'options': list(version_options.keys()),
                        'option_labels': version_options,
                        'refresh_on_change': True,
                        'advanced': False
            }
        }
        if version == "custom":
            for i, repo in enumerate(zynconf.zynthian_repositories):
                path = f"/zynthian/{repo}"
                tags = zynconf.get_git_tags(path, refresh_repos)
                branches = zynconf.get_git_branches(path, False)
                options = []
                if tags:
                    options += tags
                if branches:
                    options += branches
                options = sorted(options, key=str.casefold)
                labels = {}
                for label in tags:
                    if label == self.stable_tag:
                        labels[label] = f"{label} - stable release"
                    else:
                        labels[label] = f"{label} - freeze on this tag (no updates)"
                for label in branches:
                    if label == self.stable_branch:
                        labels[label] = f"{label} - staging branch"
                    elif label == self.testing_branch:
                        labels[label] = f"{label} - main development branch"
                    else:
                        labels[label] = label
                config[f"ZYNTHIAN_REPO_{repo}"] = {
                    'type': 'select',
                    'title': repo,
                    'value': repo_branches[i],
                    'options': options,
                    'option_labels': labels,
                    'advanced': repo in self.advanced_repository_list
                }
        config['_SPACER_'] = {
            'type': 'html',
            'content': "<br>"
        }
        return config

    def set_repo_branch(self, repo_name, branch_name):
        logging.info(f"Changing repository '{repo_name}' to branch or tag '{branch_name}'")
        repo_dir = self.zynthian_base_dir + "/" + repo_name
        current_branch = zynconf.get_git_branch(repo_dir)
        if current_branch is None:
            current_branch = zynconf.get_git_tag(repo_dir)
        if branch_name != current_branch:
            logging.info(f"... needs change: '{current_branch}' != '{branch_name}'")
            check_output(f"git -C {repo_dir} checkout .; git -C {repo_dir} checkout {branch_name}", shell=True)
            return True

# -----------------------------------------------------------------------------
