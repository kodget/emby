#!/bin/bash

# Script to rename anatomy blocks and sections

echo "=========================================="
echo "Anatomy Blocks and Sections Renaming"
echo "=========================================="
echo ""
echo "This script will:"
echo "  1. Show current anatomy structure"
echo "  2. Rename blocks and sections to new names"
echo ""
echo "Changes:"
echo "  - Anatomy Block 1 --> Upper and Lower Limb"
echo "  - Anatomy Block 2 --> TAPP"
echo "  - Subblock 1 (Block 1) --> Upper Limb"
echo "  - Subblock 2 (Block 1) --> Lower Limb"
echo "  - Subblock 1 (Block 2) --> Thorax"
echo "  - Subblock 2 (Block 2) --> Abdomen"
echo "  - Subblock 3 (Block 2) --> Pelvis"
echo "  - Subblock 4 (Block 2) --> Perineum"
echo ""
read -p "Do you want to continue? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "Cancelled."
    exit 1
fi

echo ""
echo "=========================================="
echo "Step 1: Listing current structure..."
echo "=========================================="
echo ""

# Navigate to backend directory if not already there
cd "$(dirname "$0")"

python manage.py list_anatomy_structure

echo ""
echo "=========================================="
echo "Step 2: Applying renames..."
echo "=========================================="
echo ""

python manage.py rename_anatomy_blocks

echo ""
echo "=========================================="
echo "Step 3: Verifying changes..."
echo "=========================================="
echo ""

python manage.py list_anatomy_structure

echo ""
echo "=========================================="
echo "Done!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Refresh your browser"
echo "2. Clear browser cache if needed (Ctrl+Shift+R)"
echo "3. Check the courses page to see new names"
echo ""
