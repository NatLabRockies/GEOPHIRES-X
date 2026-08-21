============
Contributing
============

Contributions are welcome and greatly appreciated. GEOPHIRES is free and open source software that is built with collaboration and knowledge sharing. Don't hesitate to reach out to `the authors <AUTHORS.rst>`__ if you are interested in contributing in any way — big or small!

GEOPHIRES Project Tenets
========================

1. **Empower Users to Develop & Deploy Geothermal Technology**: GEOPHIRES's core tenet is to serve the geothermal techno-economic analysis needs of our users including public sector, industry, and academic, especially with regards to the development and deployment of next-generation geothermal technology.

2. **Correctness & Credibility**: GEOPHIRES strives to be maximally accurate according to state-of-the-art research consensus. SME review is required for all changes.

3. **Build Open Consensus & Community**: We build geothermal industry and stakeholder consensus through open source transparency into GEOPHIRES methodology and calculations. We embrace geothermal community participation and contribution as core aspects of fostering consensus.

4. **Continuous Improvement**: GEOPHIRES is updated continuously to reflect the latest geothermal industry research and developments. Software engineering best practices including automated test coverage ensure code quality and compliance with specifications.


Feature requests and feedback
=============================

The best way to make a feature request or give feedback is to file an issue at https://github.com/NREL/GEOPHIRES-X/issues.

Bug reports
===========

`Report bugs by creating an issue here <https://github.com/NREL/GEOPHIRES-X/issues>`__.

When reporting a bug please include:

* Detailed steps to reproduce the bug.
* Your operating system name and version.
* Any details about your local setup that might be helpful in troubleshooting.


Development
===========

To get started, create your own fork of GEOPHIRES-X and clone it locally:

1. Fork NREL/GEOPHIRES-X on GitHub by going to https://github.com/NREL/GEOPHIRES-X/fork

2. Enable Actions on your fork on GitHub in your fork's Actions tab

3. Enable Pages on your fork on GitHub by going to Settings tab → Pages → Build and deployment → Set Source to "GitHub Actions"

4. Clone your fork locally in a terminal::

    cd some/path/where-you-have-your-code-projects
    git clone git@github.com:<your GitHub username>/GEOPHIRES-X.git
    cd GEOPHIRES-X

5. Continue with the Local Setup instructions below.

Local Setup
-----------

Prerequisite: Follow fork & clone instructions above.

Strongly recommended: use a Python IDE such as `PyCharm <https://www.jetbrains.com/pycharm/>`__ or `Visual Studio Code (aka VS Code) <https://code.visualstudio.com/>`__.

If you are using PyCharm, first open the the cloned repo by going to File → Open and selecting your ``GEOPHIRES-X`` directory (from the previous steps).
Run commands in a terminal with View → Tool Windows → Terminal

1. `Install virtualenv <https://virtualenv.pypa.io/en/latest/installation.html#via-pip>`__ if you don't have it already. Then set up and activate a virtual environment for the project:

   - Windows::

        python -m venv venv
        venv\Scripts\activate

   - macOS/Linux::

        python -m venv venv
        source venv/bin/activate

(If you are using PyCharm, it may prompt you to set up the virtual environment automatically, allowing you to skip this step on the command line)

2. Install package dependencies (from ``setup.py``)::

    pip install -e .
    pip install -e ".[development]"

(PyCharm may prompt you to install dependencies, making this step unnecessary to run on the command line)

3. Install `pre-commit <https://pre-commit.com/>`__ and run the command to configure it for the project (somewhat confusingly also called ``install``)::

    pip install pre-commit
    pre-commit install

You're now ready to start making changes and committing them.

4. To commit changes locally::

    git add .
    git commit -m "Your detailed description of your changes."

Note that ``pre-commit`` will run when you run ``git commit``. If your code does not pass automated checks you will have to
add fixed files (or manually fix in some cases). Example::

        (venv) ➜  GEOPHIRES-X git:(main) ✗ git commit -m "Use __future__ annotations to allow type union syntax in HIP_RA.py"
        ruff.....................................................................Passed
        black....................................................................Failed
        - hook id: black
        - files were modified by this hook

        reformatted src/hip_ra/HIP_RA.py

        All done! ✨ 🍰 ✨
        1 file reformatted.

        trim trailing whitespace.................................................Passed
        fix end of files.........................................................Passed
        debug statements (python)................................................Passed
        (venv) ➜  GEOPHIRES-X git:(main) ✗ git add src/hip_ra/HIP_RA.py && git commit -m "Use __future__ annotations to allow type union syntax in HIP_RA.py"
        ruff.....................................................................Passed
        black....................................................................Passed
        trim trailing whitespace.................................................Passed
        fix end of files.........................................................Passed
        debug statements (python)................................................Passed
        [main 8834d58] Use __future__ annotations to allow type union syntax in HIP_RA.py
         1 file changed, 4 insertions(+), 2 deletions(-)


5. Verify that tests pass with your changes. In PyCharm, you can run unit tests by right-clicking the ``tests/`` folder and selecting "Run 'Python tests in tests'".
If you want to be extra thorough you can `run tox locally <#Tox-tests>`__ but in general it is more practical to run unit tests in PyCharm locally and then let GitHub Actions on your fork run the full ``tox`` suite.

6. Push your changes to your fork::

    git push

Then, verify that Actions pass on your commit(s) on GitHub

7. Submit a pull request through the GitHub website following `the guidelines <#Pull-Request-Guidelines>`_.

Pull Request Guidelines
-----------------------

For merging, you should:

1. Ensure Actions are passing on your fork. Actions will also be automatically run when you create a PR, and they will need to be passing as a requirement to merge.
2. Add unit test coverage
3. Strive to write clean, self-documenting code. Update documentation which cannot be adequately self-documented.
4. Add yourself to `AUTHORS.rst <AUTHORS.rst>`__.
5. Major changes may merit a mention in `CHANGELOG.rst <CHANGELOG.rst>`__

Add at least one reviewer to your pull request to get it reviewed and approved.

If you need some code review or feedback while you're developing the code you can make the pull request and set it as a draft.


Tox tests
---------

To run all the ``tox`` tests locally::

    tox

Note, to combine the coverage data from all the tox environments run:

.. list-table::
    :widths: 10 90
    :stub-columns: 1

    - - Windows
      - ::

            set PYTEST_ADDOPTS=--cov-append
            tox

    - - Other
      - ::

            PYTEST_ADDOPTS=--cov-append tox


To run a subset of tests::

    tox -e envname -- pytest -k test_myfeature

To run all the test environments in *parallel*::

    tox -p auto

Use Unittests runner in Pycharm
-------------------------------
Configure Pycharm to use Unittests runner instead of pytest runner in order to see subtests. See https://intellij-support.jetbrains.com/hc/en-us/community/posts/360000024199-Python-SubTest?page=1#community_comment_14435372699538

VS Code
-------

``.vscode/settings.json`` (macOS):

.. code-block::

 {
    "python.defaultInterpreterPath": ".tox/py311/bin/python",
    "python.testing.unittestEnabled": false,
    "python.testing.unittestArgs": [
        "-v",
        "-s",
        "-p",
        "test_*.py"
    ],
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": [
        "-c",
        "pytest.ini",
        "--no-cov"
    ],
    "python.analysis.enablePytestExtra": true,
    "python.languageServer": "Pylance",
   }


``.vscode/settings.json`` (Windows):

.. code-block::

 {
    "workbench.colorTheme": "Default Dark Modern",
    "terminal.integrated.profiles.windows": {
        "PowerShell": {
          "source": "PowerShell",
          "icon": "terminal-powershell",
          "args": ["-ExecutionPolicy", "Bypass"]
        }
      },
      "terminal.integrated.defaultProfile.windows": "PowerShell",
        "python.defaultInterpreterPath": ".tox\\py310\\Scripts\\python.exe",
        "python.testing.unittestEnabled": false,
        "python.testing.unittestArgs": [
            "-v",
            "-s",
            "-p",
            "test_*.py"
        ],
        "python.testing.pytestEnabled": true,
        "python.testing.pytestArgs": [
            "-c",
            "pytest.ini",
        ],
        "python.analysis.enablePytestExtra": true,
        "python.languageServer": "Pylance",
   }

Example running example file from the terminal::

   python src\geophires_x\GEOPHIRESv3.py tests\examples\example1.txt

Version Management
------------------

This example uses remotes named ``fork`` and ``origin``:

.. code-block::

    (venv) ➜  python-geophires-x git:(main) ✗ git remote -v
    fork    git@github.com:softwareengineerprogrammer/python-geophires-x-nrel.git (fetch)
    fork    git@github.com:softwareengineerprogrammer/python-geophires-x-nrel.git (push)
    origin  git@github.com:NREL/python-geophires-x.git (fetch)
    origin  git@github.com:NREL/python-geophires-x.git (push)

Run ``bumpversion``:

.. code-block::

    (venv) ➜  python-geophires-x git:(main) bumpversion patch
    ruff.....................................................................Passed
    black....................................................................Passed
    trim trailing whitespace.................................................Passed
    fix end of files.........................................................Passed
    debug statements (python)................................................Passed

Then push both commits and tags to your fork:

.. code-block::

    (venv) ➜  python-geophires-x git:(main) git push && git push fork --tags
    Enumerating objects: 37, done.
    Counting objects: 100% (37/37), done.
    Delta compression using up to 10 threads
    Compressing objects: 100% (22/22), done.
    Writing objects: 100% (23/23), 2.94 KiB | 2.94 MiB/s, done.
    Total 23 (delta 19), reused 0 (delta 0), pack-reused 0
    remote: Resolving deltas: 100% (19/19), completed with 12 local objects.
    To github.com:softwareengineerprogrammer/python-geophires-x-nrel.git
       a6dcf71..752cff3  main -> main
    Enumerating objects: 1, done.
    Counting objects: 100% (1/1), done.
    Writing objects: 100% (1/1), 205 bytes | 205.00 KiB/s, done.
    Total 1 (delta 0), reused 0 (delta 0), pack-reused 0
    To github.com:softwareengineerprogrammer/python-geophires-x-nrel.git
     * [new tag]         v3.2.3 -> v3.2.3

Once a version bump is merged into the main repository with a Pull Request, tag must be manually pushed (GitHub `doesn't include tags in PRs <https://stackoverflow.com/questions/12278660/adding-tags-to-a-pull-request>`__):

.. code-block::

    (venv) ➜  python-geophires-x git:(main) git push origin tag v3.2.3


Documentation Updates
---------------------

If a change includes new classes with parameters that should be included in documentation,
add them to `get_parameter_sources in geophires_x_schema_generator <https://github.com/NREL/GEOPHIRES-X/blob/1f47d6207c4d1458b949ac2cc470b453951d27ac/src/geophires_x_schema_generator/__init__.py#L48-L75>`__.
Then run `geophires_x_schema_generator/main.py <https://github.com/NREL/GEOPHIRES-X/blob/main/src/geophires_x_schema_generator/main.py>`__
and commit the updated json schema files to source - `example <https://github.com/NREL/GEOPHIRES-X/pull/285/files#diff-3d85ef79807fc6c25a758a698fd3a7095750bd27ea52341700e1dad94885b5f6>`__.

``geophires_x_schema_generator/main.py`` should also be run if new parameters are added to existing classes or changes are made to existing parameters.

New classes may also be added to the appropriate module file in ``docs/reference``, i.e. `geophires_x.rst <https://github.com/NREL/GEOPHIRES-X/blob/8cf4ee9a2cc917f037ff06554c40698ef2591614/docs/reference/geophires_x.rst#L16-L15>`__

Schema Files
------------

GEOPHIRES & HIP-RA schema files generated by ``geophires_x_schema_generator`` are in an `OpenAPI Specification <https://swagger.io/docs/specification/about/>`__-compatible format.
These schema files can be used to build your own API or UI for GEOPHIRES.

* `geophires-request.json <https://github.com/NREL/GEOPHIRES-X/blob/main/src/geophires_x_schema_generator/geophires-request.json>`__
* `hip-ra-x-request.json <https://github.com/NREL/GEOPHIRES-X/blob/main/src/geophires_x_schema_generator/hip-ra-x-request.json>`__

Tips
----

git
^^^

A working understanding of `git <https://git-scm.com/>`__ is one of the most beneficial skills you can have when working on software, even if you are not a software engineer.
Although most modern IDEs now provide a reasonable GUI for working with git, learning and using git on the command line is often the most effective way
to become proficient. This is not an easy skill to learn for most, and there is no one tutorial that will substitute for real-world experience.
However the following tutorials may be a good place to start:

- https://docs.gitlab.com/ee/gitlab-basics/start-using-git.html
- https://githubtraining.github.io/training-manual/#/04_branching_with_git

zsh
^^^

Shell prompt examples above use zsh with my `Oh My Zsh <https://ohmyz.sh/>`__.
