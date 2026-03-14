# Wait, `case 'done': obj.event.set()` exists at line 287.
# Why did the code reviewer say there is no `case 'done'` and it falls through?
# Oh! Because the button data for "Add More" is `vidtool {mode}`, which means `data[1]` is `vid_vid`.
# But for "Done", the button data is `vidtool done`. `data[1]` is `done`.
# `case 'done':` is explicitly caught.
# Is `obj.extra_data.clear()` called?
