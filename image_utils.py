import os
from PIL import Image


# ============================================
# CONFIG
# ============================================

MAX_SIZE_MB = 10
MAX_WIDTH = 2000
MAX_HEIGHT = 2000

SUPPORTED_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
    ".gif",
    ".tiff"
)


# ============================================
# CHECK IMAGE FILE
# ============================================

def is_supported_image(filename):

    filename = filename.lower()

    return filename.endswith(SUPPORTED_EXTENSIONS)


# ============================================
# SAFE FILE NAME
# ============================================

def clean_filename(name):

    name = name.lower().strip()

    name = name.replace(" ", "_")

    invalid = '\\/:*?"<>|'

    for c in invalid:
        name = name.replace(c, "")

    return name


# ============================================
# CREATE FOLDER
# ============================================

def ensure_folder(folder):

    if not os.path.exists(folder):
        os.makedirs(folder)


# ============================================
# RESIZE IF TOO LARGE
# ============================================

def resize_image(image):

    w, h = image.size

    if w <= MAX_WIDTH and h <= MAX_HEIGHT:
        return image

    image.thumbnail(
        (MAX_WIDTH, MAX_HEIGHT),
        Image.Resampling.LANCZOS
    )

    return image


# ============================================
# COMPRESS PNG
# ============================================

def save_png_under_limit(image, output_path):

    image = image.convert("RGBA")

    image = resize_image(image)

    compress = 9

    image.save(
        output_path,
        format="PNG",
        optimize=True,
        compress_level=compress
    )

    while os.path.getsize(output_path) > MAX_SIZE_MB * 1024 * 1024:

        compress -= 1

        if compress < 0:
            break

        image.save(
            output_path,
            format="PNG",
            optimize=True,
            compress_level=compress
        )

    return output_path


# ============================================
# CONVERT TO PNG
# ============================================

def convert_to_png(input_path, output_path):

    img = Image.open(input_path)

    save_png_under_limit(
        img,
        output_path
    )

    return output_path


# ============================================
# SAVE INVENTORY IMAGE
# ============================================

def save_inventory_image(
    input_path,
    image_name,
    folder="img"
):

    ensure_folder(folder)

    image_name = clean_filename(image_name)

    output_path = os.path.join(
        folder,
        image_name + ".png"
    )

    convert_to_png(
        input_path,
        output_path
    )

    return output_path


# ============================================
# DELETE IMAGE
# ============================================

def delete_inventory_image(
    image_name,
    folder="img"
):

    image_name = clean_filename(image_name)

    path = os.path.join(
        folder,
        image_name + ".png"
    )

    if not os.path.exists(path):
        return False

    os.remove(path)

    return True


# ============================================
# RENAME IMAGE
# ============================================

def rename_inventory_image(
    old_name,
    new_name,
    folder="img"
):

    old_name = clean_filename(old_name)
    new_name = clean_filename(new_name)

    old_path = os.path.join(
        folder,
        old_name + ".png"
    )

    new_path = os.path.join(
        folder,
        new_name + ".png"
    )

    if not os.path.exists(old_path):
        return False

    if os.path.exists(new_path):
        return False

    os.rename(
        old_path,
        new_path
    )

    return True


# ============================================
# IMAGE EXISTS
# ============================================

def image_exists(
    image_name,
    folder="img"
):

    image_name = clean_filename(image_name)

    return os.path.exists(
        os.path.join(
            folder,
            image_name + ".png"
        )
    )


# ============================================
# LIST INVENTORY
# ============================================

def get_inventory(folder="img"):

    ensure_folder(folder)

    images = []

    for f in sorted(os.listdir(folder)):

        if f.lower().endswith(".png"):

            images.append({
                "name": os.path.splitext(f)[0],
                "path": os.path.join(folder, f),
                "size_mb": round(
                    os.path.getsize(
                        os.path.join(folder, f)
                    ) / 1024 / 1024,
                    2
                )
            })

    return images


# ============================================
# SEARCH INVENTORY
# ============================================

def search_inventory(
    keyword,
    folder="img"
):

    keyword = keyword.lower()

    result = []

    for item in get_inventory(folder):

        if keyword in item["name"].lower():
            result.append(item)

    return result


# ============================================
# INVENTORY STATISTICS
# ============================================

def inventory_statistics(folder="img"):

    items = get_inventory(folder)

    total_images = len(items)

    total_size = 0

    for item in items:
        total_size += item["size_mb"]

    return {

        "total_images": total_images,

        "total_size_mb": round(
            total_size,
            2
        )
    }