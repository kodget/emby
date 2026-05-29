# Rename Anatomy Blocks and Sections

This guide explains how to rename anatomy blocks and sections in the database.

## What Will Be Renamed

### Blocks

| Current Name    | New Name             |
| --------------- | -------------------- |
| Anatomy Block 1 | Upper and Lower Limb |
| Anatomy Block 2 | TAPP                 |

### Sections (Subblocks)

**Block 1 Sections:**
| Current Name | New Name |
|--------------|----------|
| Subblock 1 | Upper Limb |
| Subblock 2 | Lower Limb |

**Block 2 Sections:**
| Current Name | New Name |
|--------------|----------|
| Subblock 1 | Thorax |
| Subblock 2 | Abdomen |
| Subblock 3 | Pelvis |
| Subblock 4 | Perineum |

## Important Notes

⚠️ **IDs remain unchanged** - Only the display names (titles) are updated
✅ **All existing slides and materials** will continue to work
✅ **No data loss** - This only updates the `name` field in the database

## Quick Start

### Option 1: Use the Batch Script (Easiest)

**Windows:**

```cmd
cd backend
rename_anatomy.bat
```

**Linux/Mac:**

```bash
cd backend
chmod +x rename_anatomy.sh
./rename_anatomy.sh
```

### Option 2: Run Commands Manually

**Step 1: Check current structure**

```bash
cd backend
python manage.py list_anatomy_structure
```

This will show you all anatomy blocks and sections with their IDs.

**Step 2: Apply the renames**

```bash
python manage.py rename_anatomy_blocks
```

**Step 3: Verify the changes**

```bash
python manage.py list_anatomy_structure
```

## Customizing the Renames

If you need to rename different blocks or sections, edit the file:
`backend/curriculum/management/commands/rename_anatomy_blocks.py`

### Example: Adding More Renames

```python
# Block renamings
block_renames = {
    'anatomy-block-1': 'Upper and Lower Limb',
    'anatomy-block-2': 'TAPP',
    'anatomy-block-3': 'Your New Name Here',  # Add more
}

# Section renamings
section_renames = {
    'upper-limb': 'Upper Limb',
    'lower-limb': 'Lower Limb',
    'your-section-id': 'Your New Name',  # Add more
}
```

## Troubleshooting

### "Block not found" or "Section not found"

This means the ID in the script doesn't match what's in your database.

**Solution:**

1. Run `python manage.py list_anatomy_structure` to see actual IDs
2. Update the IDs in `rename_anatomy_blocks.py`
3. Run the rename command again

### Changes not showing in browser

**Solution:**

1. Clear browser cache (Ctrl+Shift+R or Cmd+Shift+R)
2. Refresh the page
3. Check if curriculum cache needs clearing

### Need to undo changes

You can run the rename command again with the old names:

```python
block_renames = {
    'anatomy-block-1': 'Block 1',  # Revert to old name
    'anatomy-block-2': 'Block 2',
}
```

## Database Direct Update (Advanced)

If you prefer to update the database directly:

```sql
-- Update blocks
UPDATE curriculum_block
SET name = 'Upper and Lower Limb'
WHERE id = 'anatomy-block-1';

UPDATE curriculum_block
SET name = 'TAPP'
WHERE id = 'anatomy-block-2';

-- Update sections
UPDATE curriculum_section
SET name = 'Upper Limb'
WHERE id = 'upper-limb';

UPDATE curriculum_section
SET name = 'Lower Limb'
WHERE id = 'lower-limb';

UPDATE curriculum_section
SET name = 'Thorax'
WHERE id = 'thorax';

UPDATE curriculum_section
SET name = 'Abdomen'
WHERE id = 'abdomen';

UPDATE curriculum_section
SET name = 'Pelvis'
WHERE id = 'pelvis';

UPDATE curriculum_section
SET name = 'Perineum'
WHERE id = 'perineum';
```

## Files Created

1. **`list_anatomy_structure.py`** - Lists all anatomy blocks and sections
2. **`rename_anatomy_blocks.py`** - Applies the renames
3. **`rename_anatomy.bat`** - Windows batch script
4. **`rename_anatomy.sh`** - Linux/Mac shell script
5. **`RENAME_ANATOMY_BLOCKS.md`** - This documentation

## After Renaming

1. ✅ Refresh your browser
2. ✅ Clear browser cache if needed
3. ✅ Check the courses page - you should see new names
4. ✅ Verify upload modal shows new names
5. ✅ Test that existing slides still work

## Support

If you encounter any issues:

1. Check the command output for error messages
2. Run `list_anatomy_structure` to verify current state
3. Check the database directly if needed
4. The IDs remain unchanged, so all relationships are preserved

## Date

2026-05-27
