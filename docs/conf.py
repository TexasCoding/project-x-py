# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys
from pathlib import Path

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.

# Add the project root to sys.path
docs_dir = Path(__file__).parent
project_root = docs_dir.parent
src_dir = project_root / "src"
sys.path.insert(0, str(src_dir))

# -- Project information -----------------------------------------------------

project = "project-x-py"
copyright = "2025, Jeff West"
author = "Jeff West"
release = "1.0.2"
version = "1.0.2"

# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.todo",
    "sphinx.ext.coverage",
    "sphinx.ext.ifconfig",
    "myst_parser",
    "sphinx_autodoc_typehints",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# Generate module index
modindex_common_prefix = ["project_x_py."]

# Enable module index generation
html_domain_indices = True
html_use_modindex = True

# Force creation of Python module index
add_module_names = False
modindex_common_prefix = ["project_x_py."]

# Note: py-modindex.rst will be built as py-modindex.html automatically

# The suffix(es) of source filenames.
source_suffix = {
    ".rst": None,
    ".md": None,
}

# The master toctree document.
master_doc = "index"

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.
html_theme = "sphinx_rtd_theme"

# Theme options are theme-specific and customize the look and feel of a theme
html_theme_options = {
    "canonical_url": "",
    "analytics_id": "",
    "logo_only": False,
    "display_version": True,
    "prev_next_buttons_location": "bottom",
    "style_external_links": False,
    "vcs_pageview_mode": "",
    "style_nav_header_background": "#2980B9",
    # Toc options
    "collapse_navigation": True,
    "sticky_navigation": True,
    "navigation_depth": 4,
    "includehidden": True,
    "titles_only": False,
}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

# Custom sidebar templates, must be a dictionary that maps document names
# to template names.
html_sidebars = {
    "**": [
        "relations.html",  # needs 'show_related': True theme option to display
        "searchbox.html",
    ]
}

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = "sphinx"

# -- Extension configuration -------------------------------------------------

# -- Options for autodoc extension ------------------------------------------

autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "special-members": "__init__",
    "undoc-members": True,
    "exclude-members": "__weakref__",
    "show-inheritance": True,
}

# Don't show typehints in the signature - they'll be shown in the description
autodoc_typehints = "description"
autodoc_typehints_description_target = "documented_params"

# -- Options for autosummary extension ---------------------------------------

autosummary_generate = True
autosummary_imported_members = True

# -- Options for Napoleon extension ------------------------------------------

napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = False
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = False
napoleon_use_admonition_for_notes = False
napoleon_use_admonition_for_references = False
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_preprocess_types = False
napoleon_type_aliases = None
napoleon_attr_annotations = True

# -- Options for intersphinx extension ---------------------------------------

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "polars": ("https://pola-rs.github.io/polars/py-polars/html/", None),
    "requests": ("https://requests.readthedocs.io/en/stable/", None),
}

# -- Options for todo extension ----------------------------------------------

todo_include_todos = True

# -- Options for MyST parser ------------------------------------------------

myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "dollarmath",
    "fieldlist",
    "html_admonition",
    "html_image",
    "replacements",
    "smartquotes",
    "substitution",
    "tasklist",
]

# -- Custom configuration ---------------------------------------------------

# Show source links
html_show_sourcelink = True

# Show copyright in footer
html_show_copyright = True

# Show last updated timestamp
html_last_updated_fmt = "%b %d, %Y"

# Custom CSS
html_css_files = [
    "custom.css",
]

# Logo and favicon
html_logo = "_static/logo.png"
html_favicon = "_static/favicon.ico"

# SEO
html_title = f"{project} {version} documentation"
html_short_title = f"{project} docs"

# GitHub integration
html_context = {
    "display_github": True,
    "github_user": "TexasCoding",
    "github_repo": "project-x-py",
    "github_version": "main",
    "conf_py_path": "/docs/",
}
