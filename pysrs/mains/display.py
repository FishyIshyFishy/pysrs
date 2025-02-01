import numpy as np
from mpl_toolkits.axes_grid1 import make_axes_locatable

def create_axes(gui, n_channels):
    gui.fig.clf()
    gui.channel_axes = []
    gui.slice_x = [None] * n_channels
    gui.slice_y = [None] * n_channels
    
    for i in range(n_channels):
        ax_main = gui.fig.add_subplot(1, n_channels, i+1)
        ax_main.set_xlabel('')
        ax_main.set_ylabel('')
        
        divider = make_axes_locatable(ax_main)
        ax_hslice = divider.append_axes("bottom", size="30%", pad=0.05, sharex=ax_main)
        ax_vslice = divider.append_axes("left", size="30%", pad=0.05, sharey=ax_main)
        
        ch_dict = {
            "main": ax_main,
            "hslice": ax_hslice,
            "vslice": ax_vslice,
            "img_handle": None,
            "colorbar": None,
            "vline": None,
            "hline": None,
        }
        gui.channel_axes.append(ch_dict)
    gui.canvas.draw()

def display_data(gui, data_list):
    if not data_list:
        return

    n_channels = len(data_list)
    if (not gui.channel_axes) or (len(gui.channel_axes) != n_channels):
        create_axes(gui, n_channels)
    
    gui.data = data_list
    for i, data in enumerate(data_list):
        ch_ax = gui.channel_axes[i]
        ax_main = ch_ax["main"]
        x_extent = np.linspace(-gui.config['amp_x'], gui.config['amp_x'], data.shape[1])
        y_extent = np.linspace(-gui.config['amp_y'], gui.config['amp_y'], data.shape[0])
        
        if ch_ax["img_handle"] is None:
            im = ax_main.imshow(
                data,
                extent=[x_extent[0], x_extent[-1], y_extent[0], y_extent[-1]],
                origin='lower',
                aspect='equal',
                cmap='cool'
            )
            ch_ax["img_handle"] = im
            ax_main.set_xlabel('')
            ax_main.set_ylabel('')
            
            gui.slice_x[i] = data.shape[1] // 2
            gui.slice_y[i] = data.shape[0] // 2
            
            ch_ax["vline"] = ax_main.axvline(x=x_extent[gui.slice_x[i]], color='red', linestyle='--', lw=2)
            ch_ax["hline"] = ax_main.axhline(y=y_extent[gui.slice_y[i]], color='blue', linestyle='--', lw=2)
            
            cax = ax_main.inset_axes([1.05, 0, 0.05, 1])
            cb = gui.fig.colorbar(im, cax=cax, orientation='vertical')
            cb.set_label('Intensity')
            ch_ax["colorbar"] = cb
        else:
            im = ch_ax["img_handle"]
            im.set_data(data)
            im.set_clim(vmin=data.min(), vmax=data.max())
            im.set_extent([x_extent[0], x_extent[-1], y_extent[0], y_extent[-1]])
        
        if ch_ax["vline"] is not None:
            ch_ax["vline"].set_xdata(x_extent[gui.slice_x[i]])
        if ch_ax["hline"] is not None:
            ch_ax["hline"].set_ydata(y_extent[gui.slice_y[i]])
        
        ax_hslice = ch_ax["hslice"]
        ax_hslice.clear()
        ax_hslice.plot(x_extent, data[gui.slice_y[i], :], color='blue')
        ax_hslice.set_xlim(x_extent[0], x_extent[-1])
        ax_hslice.set_ylabel('Intensity', fontsize=8)

        ax_vslice = ch_ax["vslice"]
        ax_vslice.clear()
        ax_vslice.plot(data[:, gui.slice_x[i]], y_extent, color='red')
        ax_vslice.set_ylim(y_extent[0], y_extent[-1])
        ax_vslice.set_xlabel('Intensity', fontsize=8)
        
    gui.canvas.draw_idle()

def on_image_click(gui, event):
    if str(gui.toolbar.mode) in ["zoom rect", "pan/zoom"]:
        return
    if not gui.channel_axes or not gui.data:
        return

    for i, ch_ax in enumerate(gui.channel_axes):
        if event.inaxes == ch_ax["main"]:
            data = gui.data[i]
            x_extent = np.linspace(-gui.config['amp_x'], gui.config['amp_x'], data.shape[1])
            y_extent = np.linspace(-gui.config['amp_y'], gui.config['amp_y'], data.shape[0])
            
            gui.slice_x[i] = int(np.abs(x_extent - event.xdata).argmin())
            gui.slice_y[i] = int(np.abs(y_extent - event.ydata).argmin())
            
            if ch_ax["vline"] is not None:
                ch_ax["vline"].set_xdata(x_extent[gui.slice_x[i]])
            if ch_ax["hline"] is not None:
                ch_ax["hline"].set_ydata(y_extent[gui.slice_y[i]])
            
            display_data(gui, gui.data)
            return
