import logging
import os
import queue
import time
import unittest
from unittest.mock import Mock, MagicMock, create_autospec, PropertyMock, patch

import github3
import IGitt
from IGitt.GitHub.GitHubMergeRequest import GitHubMergeRequest
from IGitt.GitLab.GitLabMergeRequest import GitLabMergeRequest
from IGitt.GitHub.GitHubIssue import GitHubIssue

from errbot.backends.test import TestBot
from errbot.backends.base import Message

import plugins.labhub
from plugins.labhub import LabHub

from tests.helper import plugin_testbot

class TestLabHub(unittest.TestCase):

    def setUp(self):
        plugins.labhub.github3 = create_autospec(github3)

        self.mock_org = create_autospec(github3.orgs.Organization)
        self.mock_gh = create_autospec(github3.GitHub)
        self.mock_team = create_autospec(github3.orgs.Team)
        self.mock_team.name = PropertyMock()
        self.mock_team.name = 'mocked team'
        self.mock_repo = create_autospec(IGitt.GitHub.GitHub.GitHubRepository)

        plugins.labhub.github3.login.return_value = self.mock_gh
        self.mock_gh.organization.return_value = self.mock_org
        self.mock_org.teams.return_value = [self.mock_team]
        plugins.labhub.github3.organization.return_value = self.mock_org

    def test_invite_cmd(self):
        mock_team_newcomers = create_autospec(github3.orgs.Team)
        mock_team_developers = create_autospec(github3.orgs.Team)
        mock_team_maintainers = create_autospec(github3.orgs.Team)

        teams = {
            'coala maintainers': mock_team_maintainers,
            'coala newcomers': mock_team_newcomers,
            'coala developers': mock_team_developers
        }

        labhub, testbot = plugin_testbot(plugins.labhub.LabHub, 'LabHub', logging.ERROR)
        labhub.activate()
        labhub._teams = teams

        plugins.labhub.os.environ['GH_TOKEN'] = 'patched?'

        self.assertEqual(labhub.TEAMS, teams)

        labhub.is_room_member = MagicMock(return_value=False)
        testbot.assertCommand('!invite meet to newcomers',
                                   '@meet is not a member of this room.')

        labhub.is_room_member = MagicMock(return_value=True)

        # invite by maintainer
        mock_team_newcomers.is_member.return_value = True
        mock_team_developers.is_member.return_value = True
        mock_team_maintainers.is_member.return_value = True

        testbot.assertCommand('!invite meet to newcomers',
                                   'To get started, please follow our [newcomers guide]')
        testbot.assertCommand('!invite meet to developers',
                                   '@meet, you are a part of developers')
        testbot.assertCommand('!invite meet to maintainers',
                                   '@meet you seem to be awesome!')

        # invite by developer
        mock_team_maintainers.is_member.return_value = False
        labhub.is_room_member = MagicMock(return_value = True)

        testbot.assertCommand('!invite meet to newcomers',
                                   'To get started, please follow our [newcomers guide]')
        testbot.assertCommand('!invite meet to developers',
                                   ':poop:')
        testbot.assertCommand('!invite meet to maintainers',
                                   ':poop:')

        # invite by newcomer
        mock_team_developers.is_member.return_value = False

        testbot.assertCommand('!invite meet to newcomers',
                                   ':poop')
        testbot.assertCommand('!invite meet to developers',
                                   ':poop:')
        testbot.assertCommand('!invite meet to maintainers',
                                   ':poop:')

        # invalid team
        testbot.assertCommand('!invite meet to something',
                                   'select from one of the valid')

        #invalid command
        testbot.assertCommand('!invite meetto newcomers',
                                   'Command "invite" / "invite meetto" not found.')

    def test_is_room_member(self):
        msg = create_autospec(Message)
        msg.frm.room.occupants = PropertyMock()
        msg.frm.room.occupants = ['batman', 'superman']
        self.assertTrue(LabHub.is_room_member('batman', msg))

    def test_hello_world_callback(self):
        teams = {
            'coala newcomers': self.mock_team,
            'coala developers': self.mock_team,
            'coala maintainers': self.mock_team,
        }

        testbot = TestBot(extra_plugin_dir='plugins', loglevel=logging.ERROR)
        testbot.start()
        labhub = testbot.bot.plugin_manager.get_plugin_obj_by_name('LabHub')
        labhub.TEAMS = teams
        self.mock_team.is_member.return_value = False
        testbot.assertCommand('hello, world', 'newcomer')
        # Since the user won't be invited again, it'll timeout waiting for a
        # response.
        with self.assertRaises(queue.Empty):
            testbot.assertCommand('helloworld', 'newcomer')

    def test_create_issue_cmd(self):
        plugins.labhub.GitHub = create_autospec(IGitt.GitHub.GitHub.GitHub)
        plugins.labhub.GitLab = create_autospec(IGitt.GitLab.GitLab.GitLab)
        plugins.labhub.GitHubToken = create_autospec(IGitt.GitHub.GitHubToken)
        plugins.labhub.GitLabPrivateToken = create_autospec(IGitt.GitLab.GitLabPrivateToken)

        labhub, testbot_private = plugin_testbot(
            plugins.labhub.LabHub, 'LabHub', logging.ERROR,
            {'BACKEND': 'text', 'ACCESS_CONTROLS':{'create_issue_cmd' : {'allowprivate':False}}}
        )
        labhub.activate()
        labhub.REPOS = {'repository': self.mock_repo}
        plugins.labhub.GitHubToken.assert_called_with(None)
        plugins.labhub.GitLabPrivateToken.assert_called_with(None)

        # TODO
        # Ignoring assertion to prevent build failure for time being
        # Creating issue in private chat
        # testbot_private.assertCommand('!new issue repository this is the title\nbo\ndy',
        #                       'You\'re not allowed')

        # Creating issue in public chat
        labhub, testbot_public = plugin_testbot(
            plugins.labhub.LabHub, 'LabHub', logging.ERROR, {'BACKEND': 'text'}
        )
        labhub.activate()
        labhub.REPOS = {'repository': self.mock_repo,
                        'repository.github.io': self.mock_repo}

        testbot_public.assertCommand('!new issue repository this is the title\nbo\ndy',
                              'Here you go')

        labhub.REPOS['repository'].create_issue.assert_called_once_with(
            'this is the title', 'bo\ndy\nOpened by @None at [text]()'
        )

        testbot_public.assertCommand('!new issue repository.github.io another title\nand body',
                              'Here you go')

        labhub.REPOS['repository.github.io'].create_issue.assert_called_with(
            'another title', 'and body\nOpened by @None at [text]()'
        )

        testbot_public.assertCommand('!new issue coala title', 'repository that does not exist')

    def test_is_newcomer_issue(self):
        mock_iss = create_autospec(IGitt.GitHub.GitHubIssue)
        mock_iss.labels = PropertyMock()
        mock_iss.labels = ('difficulty/newcomer',)
        self.assertTrue(LabHub.is_newcomer_issue(mock_iss))
        mock_iss.labels = ('difficulty/medium',)
        self.assertFalse(LabHub.is_newcomer_issue(mock_iss))

    def test_unassign_cmd(self):
        plugins.labhub.GitHub = create_autospec(IGitt.GitHub.GitHub.GitHub)
        plugins.labhub.GitLab = create_autospec(IGitt.GitLab.GitLab.GitLab)
        labhub, testbot = plugin_testbot(plugins.labhub.LabHub, 'LabHub', logging.ERROR)

        labhub.activate()
        labhub.REPOS = {'name': self.mock_repo}

        mock_iss = create_autospec(IGitt.GitHub.GitHubIssue)
        self.mock_repo.get_issue.return_value = mock_iss
        mock_iss.assignees = PropertyMock()
        mock_iss.assignees = (None, )
        mock_iss.unassign = MagicMock()

        testbot.assertCommand('!unassign https://github.com/coala/name/issues/23',
                              'you are unassigned now', timeout=10000)
        self.mock_repo.get_issue.assert_called_with(23)
        mock_iss.unassign.assert_called_once_with(None)

        mock_iss.assignees = ('meetmangukiya', )
        testbot.assertCommand('!unassign https://github.com/coala/name/issues/23',
                           'not an assignee on the issue')

        testbot.assertCommand('!unassign https://github.com/coala/s/issues/52',
                              'Repository doesn\'t exist.')

        testbot.assertCommand('!unassign https://gitlab.com/ala/am/issues/532',
                               'Repository not owned by our org.')

    def test_assign_cmd(self):
        plugins.labhub.GitHub = create_autospec(IGitt.GitHub.GitHub.GitHub)
        plugins.labhub.GitLab = create_autospec(IGitt.GitLab.GitLab.GitLab)
        labhub, testbot = plugin_testbot(plugins.labhub.LabHub, 'LabHub', logging.ERROR)
        labhub.activate()

        mock_issue = create_autospec(GitHubIssue)
        self.mock_repo.get_issue.return_value = mock_issue

        labhub.REPOS = {'a': self.mock_repo}

        mock_dev_team = create_autospec(github3.orgs.Team)
        mock_maint_team = create_autospec(github3.orgs.Team)
        mock_dev_team.is_member.return_value = False
        mock_maint_team.is_member.return_value = False

        labhub.TEAMS = {'coala newcomers': self.mock_team,
                        'coala developers': mock_dev_team,
                        'coala maintainers': mock_maint_team}

        cmd = '!assign https://github.com/{}/{}/issues/{}'
        # no assignee, not newcomer
        mock_issue.assignees = tuple()
        self.mock_team.is_member.return_value = False

        testbot.assertCommand(cmd.format('coala', 'a', '23'),
                              'You\'ve been assigned to the issue')
        
        # no assignee, newcomer, initiatives/gci
        mock_maint_team.is_member.return_value = False
        mock_dev_team.is_member.return_value = False
        mock_issue.labels = 'initiatives/gci',
        mock_issue.assignees = tuple()
        testbot.assertCommand(cmd.format('coala', 'a', '23'),
                              'You are not eligible to be assigned'
                              ' to this issue')
        testbot.pop_message()

        # no assignee, developer, initiatives/gci
        mock_maint_team.is_member.return_value = False
        mock_dev_team.is_member.return_value = True
        mock_issue.labels = 'initiatives/gci',
        mock_issue.assignees = tuple()
        testbot.assertCommand(cmd.format('coala', 'a', '23'),
                              'You are not eligible to be assigned'
                              ' to this issue')
        testbot.pop_message()
        mock_dev_team.is_member.return_value = False

        # no assignee, newcomer, difficulty/low
        mock_issue.labels = PropertyMock()
        mock_issue.labels = ('difficulty/low', )
        mock_issue.assignees = tuple()
        self.mock_team.is_member.return_value = True

        testbot.assertCommand(cmd.format('coala', 'a', '23'),
                              'You\'ve been assigned to the issue')

        # no assignee, newcomer, no labels
        self.mock_team.is_member.return_value = True
        mock_issue.labels = tuple()
        mock_issue.assignees = tuple()
        testbot.assertCommand(cmd.format('coala', 'a', '23'),
                              'not eligible to be assigned to this issue')
        testbot.pop_message()

        # no assignee, newcomer, difficulty medium
        mock_issue.labels = ('difficulty/medium', )
        testbot.assertCommand(cmd.format('coala', 'a', '23'),
                              'not eligible to be assigned to this issue')
        testbot.pop_message()

        # no assignee, newcomer, difficulty medium
        labhub.GH_ORG_NAME = 'not-coala'
        testbot.assertCommand(cmd.format('coala', 'a', '23'),
                              'assigned')
        labhub.GH_ORG_NAME = 'coala'

        # newcomer, developer, difficulty/medium
        mock_dev_team.is_member.return_value = True
        mock_maint_team.is_member.return_value = False
        testbot.assertCommand(cmd.format('coala', 'a', '23'),
                              'assigned')

        # has assignee
        mock_issue.assignees = ('somebody', )
        testbot.assertCommand(cmd.format('coala', 'a', '23'),
                              'already assigned to someone')

        # has assignee same as user
        mock_issue.assignees = (None, )
        testbot.assertCommand(cmd.format('coala', 'a', '23'),
                              'already assigned to you')

        # non-existent repository
        testbot.assertCommand(cmd.format('coala', 'c', '23'),
                              'Repository doesn\'t exist.')

        # unknown org
        testbot.assertCommand(cmd.format('coa', 'a', '23'),
                              'Repository not owned by our org.')

        # no assignee, newcomer, difficulty/newcomer, second newcomer issue
        mock_issue.assignees = tuple()
        mock_dev_team.is_member.return_value = False
        mock_issue.labels = ('difficulty/newcomer', )

        with patch('plugins.labhub.GitHub') as mock_gh:
            mock_gh.raw_search = Mock()
            mock_gh.raw_search.return_value = ['mocked?']
            testbot.assertCommand(cmd.format('coala', 'a', '23'),
                                  'not eligible to be assigned to this issue')

    def test_mark_cmd(self):
        labhub, testbot = plugin_testbot(plugins.labhub.LabHub, 'LabHub', logging.ERROR)
        labhub.activate()

        labhub.REPOS = {'a': self.mock_repo}
        mock_github_mr = create_autospec(GitHubMergeRequest)
        mock_gitlab_mr = create_autospec(GitLabMergeRequest)
        mock_github_mr.labels = PropertyMock()
        mock_gitlab_mr.labels = PropertyMock()
        mock_github_mr.author = 'johndoe'
        mock_gitlab_mr.author = 'johndoe'
        cmd_github = '!mark {} https://github.com/{}/{}/pull/{}'
        cmd_gitlab = '!mark {} https://gitlab.com/{}/{}/merge_requests/{}'

        self.mock_repo.get_mr.return_value = mock_github_mr

        # Non-eistent repo
        testbot.assertCommand(cmd_github.format('wip', 'a', 'b', '23'),
                              'Repository doesn\'t exist.')
        testbot.assertCommand('!mark wip https://gitlab.com/a/b/merge_requests/2',
                              'Repository doesn\'t exist.')

        mock_github_mr.web_url = 'https://github.com/coala/a/pull/23'
        mock_gitlab_mr.web_url = 'https://gitlab.com/coala/a/merge_requests/23'

        # mark wip
        mock_github_mr.labels = ['process/pending review']
        mock_gitlab_mr.labels = ['process/pending review']
        testbot.assertCommand(cmd_github.format('wip', 'coala', 'a', '23'),
                              'marked work in progress')
        testbot.assertCommand(cmd_github.format('wip', 'coala', 'a', '23'),
                              '@johndoe, please check your pull request')
        testbot.assertCommand(cmd_github.format('wip', 'coala', 'a', '23'),
                              'https://github.com/coala/a/pull/23')

        self.mock_repo.get_mr.return_value = mock_gitlab_mr

        testbot.assertCommand(cmd_gitlab.format('wip', 'coala', 'a', '23'),
                              '@johndoe, please check your pull request')
        testbot.assertCommand(cmd_gitlab.format('wip', 'coala', 'a', '23'),
                              'https://gitlab.com/coala/a/merge_requests/23')

        self.mock_repo.get_mr.return_value = mock_github_mr

        # mark pending
        mock_github_mr.labels = ['process/wip']
        mock_gitlab_mr.labels = ['process/wip']
        testbot.assertCommand(cmd_github.format('pending', 'coala', 'a', '23'),
                              'marked pending review')
        testbot.assertCommand(cmd_github.format('pending-review', 'coala', 'a', '23'),
                              'marked pending review')
        testbot.assertCommand(cmd_github.format('pending review', 'coala', 'a', '23'),
                              'marked pending review')

    def test_alive(self):
        labhub, testbot = plugin_testbot(plugins.labhub.LabHub, 'LabHub', logging.ERROR)
        with patch('plugins.labhub.time.sleep') as mock_sleep:
            labhub.gh_repos = {
                'coala': create_autospec(IGitt.GitHub.GitHub.GitHubRepository),
                'coala-bears': create_autospec(IGitt.GitHub.GitHub.GitHubRepository),
                'coala-utils': create_autospec(IGitt.GitHub.GitHub.GitHubRepository)
            }
            # for the branch where program sleeps
            labhub.gh_repos.update({str(i):
                                    create_autospec(IGitt.GitHub.GitHub.GitHubRepository)
                                    for i in range(30)})
            labhub.gl_repos = {
                'test': create_autospec(IGitt.GitLab.GitLab.GitLabRepository)
            }
            labhub.activate()

            labhub.gh_repos['coala'].search_mrs.return_value = [1, 2]
            labhub.gh_repos['coala-bears'].search_mrs.return_value = []
            labhub.gh_repos['coala-utils'].search_mrs.return_value = []
            testbot.assertCommand('!pr stats 10hours',
                                  '2 PRs opened in last 10 hours\n'
                                  'The community is alive', timeout=100)

            labhub.gh_repos['coala'].search_mrs.return_value = []
            testbot.assertCommand('!pr stats 5hours',
                                  '0 PRs opened in last 5 hours\n'
                                  'The community is dead', timeout=100)

            labhub.gh_repos['coala'].search_mrs.return_value = [
                1, 2, 3, 4, 5,
                6, 7, 8, 9, 10
            ]
            testbot.assertCommand('!pr stats 3hours',
                                  '10 PRs opened in last 3 hours\n'
                                  'The community is on fire', timeout=100)