# Complete Blocks and Sections Renaming Guide

## Overview

This guide covers renaming all anatomy and physiology blocks and sections to their proper names.

## What Will Be Renamed

### ANATOMY BLOCKS

#### Block 1: Upper and Lower Limb

| Current         | New Name                 |
| --------------- | ------------------------ |
| Anatomy Block 1 | **Upper and Lower Limb** |
| Subblock 1      | **Upper Limb**           |
| Subblock 2      | **Lower Limb**           |

#### Block 2: TAPP

| Current         | New Name     |
| --------------- | ------------ |
| Anatomy Block 2 | **TAPP**     |
| Subblock 1      | **Thorax**   |
| Subblock 2      | **Abdomen**  |
| Subblock 3      | **Pelvis**   |
| Subblock 4      | **Perineum** |

#### Block 3: Head and Neck and Neuroanatomy

| Current         | New Name                           |
| --------------- | ---------------------------------- |
| Anatomy Block 3 | **Head and Neck and Neuroanatomy** |
| Subblock 1      | **Head and Neck**                  |
| Subblock 2      | **Neuroanatomy**                   |

---

### PHYSIOLOGY BLOCKS

#### Block 1: Physiology Block 1

| Current            | New Name                     |
| ------------------ | ---------------------------- |
| Physiology Block 1 | **Physiology Block 1**       |
| Subblock 1         | **General Physiology**       |
| Subblock 2         | **Autoregulation**           |
| Subblock 3         | **Blood and Body Fluids**    |
| Subblock 4         | **Neuromuscular Physiology** |

#### Block 2: Physiology Block 2

| Current            | New Name                        |
| ------------------ | ------------------------------- |
| Physiology Block 2 | **Physiology Block 2**          |
| Subblock 1         | **Respiratory Physiology**      |
| Subblock 2         | **Cardiovascular Physiology**   |
| Subblock 3         | **Gastrointestinal Physiology** |
| Subblock 4         | **Nutrient Metabolism**         |

#### Block 3: Physiology Block 3

| Current            | New Name                    |
| ------------------ | --------------------------- |
| Physiology Block 3 | **Physiology Block 3**      |
| Subblock 1         | **Renal Physiology**        |
| Subblock 2         | **Endocrinology**           |
| Subblock 3         | **Reproductive Physiology** |

#### Block 4: Physiology Block 4

| Current            | New Name               |
| ------------------ | ---------------------- |
| Physiology Block 4 | **Physiology Block 4** |
| Subblock 1         | **Sensory System**     |
| Subblock 2         | **Special Senses**     |
| Subblock 3         | **Motor System**       |
| Subblock 4         | **Integrating Centre** |

---

### UNCHANGED

- ✅ **Histology** blocks and sections remain unchanged
- ✅ **Embryology** blocks and sections remain unchanged
- ✅ **Medical Biochemistry** blocks and sections remain unchanged

---

## How to Run

### Quick Start (Recommended)

```cmd
cd backend
rename_anatomy.bat
```

This will:

1. Show current structure
2. Apply all renames
3. Verify changes
4. Confirm completion

### Manual Steps

```cmd
cd backend

REM Step 1: See what you have now
python manage.py list_anatomy_structure

REM Step 2: Apply all renames
python manage.py rename_anatomy_blocks

REM Step 3: Verify everything worked
python manage.py list_anatomy_structure
```

---

## Total Changes

- **7 Blocks** will be renamed
- **26 Sections** will be renamed
- **33 Total updates**

---

## Important Notes

✅ **Safe Operation**

- Only updates the `name` field (display name)
- IDs remain unchanged
- All relationships preserved
- No data loss

✅ **Backward Compatible**

- All existing slides continue to work
- All materials continue to work
- All user progress preserved

✅ **Can Be Undone**

- Just edit the script with old names
- Run it again to revert

---

## After Running

1. **Refresh Browser** (Ctrl+Shift+R)
2. **Clear Cache** if needed
3. **Check Courses Page** - New names should appear
4. **Test Upload Modal** - New names in dropdowns
5. **Verify Slides** - All existing slides still work

---

## Troubleshooting

### "Block not found" or "Section not found"

**Cause:** The ID in the script doesn't match your database

**Solution:**

1. Run: `python manage.py list_anatomy_structure`
2. Find the actual IDs in the output
3. Edit `rename_anatomy_blocks.py` with correct IDs
4. Run the rename command again

### Changes not showing

**Solution:**

1. Hard refresh: Ctrl+Shift+R (Windows) or Cmd+Shift+R (Mac)
2. Clear browser cache completely
3. Close and reopen browser
4. Check if curriculum cache needs clearing

### Need to verify database

```sql
-- Check anatomy blocks
SELECT id, name FROM curriculum_block
WHERE subject_id = 'anatomy'
ORDER BY "order";

-- Check physiology blocks
SELECT id, name FROM curriculum_block
WHERE subject_id = 'physiology'
ORDER BY "order";

-- Check all sections
SELECT id, name, block_id FROM curriculum_section
ORDER BY block_id, "order";
```

---

## Files Involved

1. **`rename_anatomy_blocks.py`** - Main rename logic
2. **`list_anatomy_structure.py`** - Shows current structure
3. **`rename_anatomy.bat`** - Windows script
4. **`rename_anatomy.sh`** - Linux/Mac script
5. **`COMPLETE_RENAME_GUIDE.md`** - This file

---

## Example Output

```
==========================================
Blocks and Sections Renaming
==========================================

=== Updating Blocks ===
✓ Updated block: anatomy-block-1 → Upper and Lower Limb
✓ Updated block: anatomy-block-2 → TAPP
✓ Updated block: anatomy-block-3 → Head and Neck and Neuroanatomy
✓ Updated block: physiology-block-1 → Physiology Block 1
✓ Updated block: physiology-block-2 → Physiology Block 2
✓ Updated block: physiology-block-3 → Physiology Block 3
✓ Updated block: physiology-block-4 → Physiology Block 4

=== Updating Sections ===
✓ Updated section: upper-limb → Upper Limb
✓ Updated section: lower-limb → Lower Limb
✓ Updated section: thorax → Thorax
... (and 23 more sections)

==========================================
Renaming complete!
  Total updates: 33
==========================================
```

---

## Ready to Run?

```cmd
cd backend
rename_anatomy.bat
```

**That's it!** The script will handle everything automatically. 🎉

---

## Date

2026-05-27
