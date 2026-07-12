import webbrowser
import time

links = [
    "https://disclosure.bursamalaysia.com/FileAccess/viewHtml?e=3663866",
    "https://disclosure.bursamalaysia.com/FileAccess/viewHtml?e=3638981",
    "https://disclosure.bursamalaysia.com/FileAccess/viewHtml?e=3602746",
    "https://disclosure.bursamalaysia.com/FileAccess/viewHtml?e=3575230",
    "https://disclosure.bursamalaysia.com/FileAccess/viewHtml?e=3551333",
    "https://disclosure.bursamalaysia.com/FileAccess/viewHtml?e=3527578",
    "https://disclosure.bursamalaysia.com/FileAccess/viewHtml?e=3495486",
    "https://disclosure.bursamalaysia.com/FileAccess/viewHtml?e=3468783",
    "https://disclosure.bursamalaysia.com/FileAccess/viewHtml?e=3445748",
    "https://disclosure.bursamalaysia.com/FileAccess/viewHtml?e=3425128",
    "https://disclosure.bursamalaysia.com/FileAccess/viewHtml?e=3396795",
    "https://disclosure.bursamalaysia.com/FileAccess/viewHtml?e=3373446",
    "https://disclosure.bursamalaysia.com/FileAccess/viewHtml?e=3348571",
    "https://disclosure.bursamalaysia.com/FileAccess/viewHtml?e=3330221",
    "https://disclosure.bursamalaysia.com/FileAccess/viewHtml?e=3303756",
    "https://disclosure.bursamalaysia.com/FileAccess/viewHtml?e=3280661",
    "https://disclosure.bursamalaysia.com/FileAccess/viewHtml?e=3255145",
    "https://disclosure.bursamalaysia.com/FileAccess/viewHtml?e=3237100",
    "https://disclosure.bursamalaysia.com/FileAccess/viewHtml?e=3206244",
    "https://disclosure.bursamalaysia.com/FileAccess/viewHtml?e=3180512",
    "https://disclosure.bursamalaysia.com/FileAccess/viewHtml?e=3154774",
    "https://disclosure.bursamalaysia.com/FileAccess/viewHtml?e=3133616",
    "https://disclosure.bursamalaysia.com/FileAccess/viewHtml?e=3101781",
    "https://disclosure.bursamalaysia.com/FileAccess/viewHtml?e=3074237",
    "https://disclosure.bursamalaysia.com/FileAccess/viewHtml?e=3027431",
    "https://disclosure.bursamalaysia.com/FileAccess/viewHtml?e=2999904",
    "https://disclosure.bursamalaysia.com/FileAccess/viewHtml?e=2977068",
    "https://disclosure.bursamalaysia.com/FileAccess/viewHtml?e=2952496",
    "https://disclosure.bursamalaysia.com/FileAccess/viewHtml?e=2931162",
]

for link in links:
    webbrowser.open(link)
    time.sleep(2)
