#!/usr/bin/env python3
"""
Documentation build script for project-x-py

This script provides an easy way to build the documentation with various options.

Usage:
    python scripts/build-docs.py [options]

Options:
    --clean         Clean build directory before building
    --open          Open documentation in browser after building
    --serve         Start live reload server
    --check-links   Check for broken links
    --coverage      Generate documentation coverage report
    --pdf           Also build PDF documentation
    --help          Show this help message

Examples:
    python scripts/build-docs.py
    python scripts/build-docs.py --clean --open
    python scripts/build-docs.py --serve
    python scripts/build-docs.py --check-links --coverage
"""

import argparse
import os
import subprocess
import sys
import webbrowser
from pathlib import Path


def run_command(cmd, cwd=None, capture_output=False):
    """Run a shell command and return the result."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=capture_output,
            text=True,
            check=True,
        )
        return result
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed: {cmd}")
        print(f"   Error: {e}")
        if capture_output:
            print(f"   Output: {e.stdout}")
            print(f"   Error output: {e.stderr}")
        sys.exit(1)


def check_dependencies():
    """Check if required dependencies are installed."""
    try:
        import myst_parser
        import sphinx
        import sphinx_rtd_theme

        print("✅ Documentation dependencies found")
        return True
    except ImportError as e:
        print(f"❌ Missing documentation dependencies: {e}")
        print("   Install with: uv sync --extra docs")
        return False


def clean_build_dir(docs_dir):
    """Clean the documentation build directory."""
    build_dir = docs_dir / "_build"
    if build_dir.exists():
        print("🧹 Cleaning build directory...")
        if sys.platform == "win32":
            run_command(f"rmdir /s /q {build_dir}", cwd=docs_dir)
        else:
            run_command(f"rm -rf {build_dir}", cwd=docs_dir)
        print("✅ Build directory cleaned")
    else:
        print("ℹ️  Build directory already clean")


def build_html(docs_dir):
    """Build HTML documentation."""
    print("📚 Building HTML documentation...")

    if sys.platform == "win32":
        run_command("make.bat html", cwd=docs_dir)
    else:
        run_command("make html", cwd=docs_dir)

    print("✅ HTML documentation built successfully")
    return docs_dir / "_build" / "html" / "index.html"


def build_pdf(docs_dir):
    """Build PDF documentation."""
    print("📄 Building PDF documentation...")

    if sys.platform == "win32":
        run_command("make.bat latexpdf", cwd=docs_dir)
    else:
        run_command("make latexpdf", cwd=docs_dir)

    print("✅ PDF documentation built successfully")


def check_links(docs_dir):
    """Check for broken links in documentation."""
    print("🔗 Checking for broken links...")

    if sys.platform == "win32":
        result = run_command("make.bat linkcheck", cwd=docs_dir, capture_output=True)
    else:
        result = run_command("make linkcheck", cwd=docs_dir, capture_output=True)

    print("✅ Link checking completed")

    # Check if any broken links were found
    if "broken" in result.stdout.lower():
        print("⚠️  Some broken links were found - check the output above")
    else:
        print("✅ No broken links found")


def check_coverage(docs_dir):
    """Generate documentation coverage report."""
    print("📊 Checking documentation coverage...")

    if sys.platform == "win32":
        run_command("make.bat coverage", cwd=docs_dir)
    else:
        run_command("make coverage", cwd=docs_dir)

    print("✅ Documentation coverage report generated")


def serve_docs(docs_dir):
    """Start live reload server for documentation."""
    print("🚀 Starting live reload server...")
    print("   Documentation will be available at http://localhost:8000")
    print("   Press Ctrl+C to stop the server")

    try:
        # Try to use sphinx-autobuild if available
        run_command("sphinx-autobuild . _build/html", cwd=docs_dir)
    except:
        print(
            "⚠️  sphinx-autobuild not found, install with: uv add --dev sphinx-autobuild"
        )
        print("   Falling back to regular build...")
        index_file = build_html(docs_dir)
        open_in_browser(index_file)


def open_in_browser(html_file):
    """Open documentation in default browser."""
    if html_file.exists():
        print(f"🌐 Opening documentation in browser...")
        webbrowser.open(f"file://{html_file.absolute()}")
    else:
        print("❌ HTML file not found - build may have failed")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Build project-x-py documentation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Examples:")[1]
        if __doc__ and "Examples:" in __doc__
        else "",
    )

    parser.add_argument(
        "--clean", action="store_true", help="Clean build directory first"
    )
    parser.add_argument(
        "--open", action="store_true", help="Open in browser after building"
    )
    parser.add_argument("--serve", action="store_true", help="Start live reload server")
    parser.add_argument(
        "--check-links", action="store_true", help="Check for broken links"
    )
    parser.add_argument(
        "--coverage", action="store_true", help="Generate coverage report"
    )
    parser.add_argument(
        "--pdf", action="store_true", help="Also build PDF documentation"
    )

    args = parser.parse_args()

    # Find project root and docs directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    docs_dir = project_root / "docs"

    if not docs_dir.exists():
        print(f"❌ Documentation directory not found: {docs_dir}")
        sys.exit(1)

    print(f"🏗️  Building documentation for project-x-py")
    print(f"   Project root: {project_root}")
    print(f"   Docs directory: {docs_dir}")
    print()

    # Check dependencies
    if not check_dependencies():
        sys.exit(1)

    # Handle serve mode
    if args.serve:
        serve_docs(docs_dir)
        return

    # Clean if requested
    if args.clean:
        clean_build_dir(docs_dir)

    # Build HTML documentation
    index_file = build_html(docs_dir)

    # Build PDF if requested
    if args.pdf:
        build_pdf(docs_dir)

    # Check links if requested
    if args.check_links:
        check_links(docs_dir)

    # Generate coverage report if requested
    if args.coverage:
        check_coverage(docs_dir)

    # Open in browser if requested
    if args.open:
        open_in_browser(index_file)

    print()
    print("🎉 Documentation build completed!")
    print(f"   HTML: {index_file}")
    if args.pdf:
        pdf_file = docs_dir / "_build" / "latex" / "project-x-py.pdf"
        print(f"   PDF: {pdf_file}")


if __name__ == "__main__":
    main()
