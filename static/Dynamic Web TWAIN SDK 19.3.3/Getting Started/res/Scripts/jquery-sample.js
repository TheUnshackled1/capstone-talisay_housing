var Enum_Demos = {
  'helloworld': 'demo01',
  'removeblankpage': 'demo02',
  'customscan': 'demo03',
  'remotescan':'demo04',
  'imageeditor': 'demo16',
  'navigation': 'demo05',
  'thumbnails': 'demo06',
  'saveimage': 'demo07',
	'httpupload': 'demo08',
  'loadlocal': 'demo09',
  'httpdownload': 'demo10',
  'scanbarcode': 'demo11',
  'scanwebcam': 'demo12',
  'mobilewebcapture': 'demo13',
  'rasterizer': 'demo14',
  'mrc': 'demo15',

},
    aryDemo = {
        categories:
            [
                {
                    name: "Scan", type: "core", demos:
                        [
							{
                                name: "Hello World",
                                API: [
                                    {
                                        name: "SelectSourceAsync()", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/WebTwain_Acquire.html?ver=latest#selectsourceasync"
                                    },
                                    {
                                        name: "AcquireImageAsync()", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/WebTwain_Acquire.html?ver=latest#acquireimageasync"
                                    }],
                                desc: "Hello World of Dynamic Web TWAIN", link: "../Samples/I_Scan-Documents/Hello-World.html", className: Enum_Demos.helloworld, screenshotLink: ""
                            },
                            {
                                name: 'Auto Remove Blank Page',
                                API: [
                                    {
                                        name: "SelectSourceAsync()", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/WebTwain_Acquire.html?ver=latest#selectsourceasync"
                                    },
                                    {
                                        name: "AcquireImageAsync()", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/WebTwain_Acquire.html?ver=latest#acquireimageasync"
                                    }],
                                desc: "Auto Remove Blank Page", link: "../Samples/I_Scan-Documents/Auto-Remove-Blank-Page.html", className: Enum_Demos.removeblankpage, screenshotLink: ""
                            },
                            {
                                name: 'Scan with Custom Settings',
                                API: [
                                    {
                                        name: "SelectDeviceAsync()", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/WebTwain_Acquire.html#selectdeviceasync"
                                    },
                                    {
                                        name: "AcquireImageAsync()", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/WebTwain_Acquire.html?ver=latest#acquireimageasync"
                                    }],
                                desc: "Scan image with customized resolution and pixel type", link: "../Samples/I_Scan-Documents/Scan-with-Custom-Settings.html", className: Enum_Demos.customscan, screenshotLink: ""
                            }
                        ]
                },
				{
                    name: "Viewer/Editor", type: "core", demos:
                        [     {
                                name: 'Built-in image viewer and editor',
                                API: [
                                    {
                                        name: "createImageEditor", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/WebTwain_Viewer.html#createimageeditor"
                                    }],
                                desc: "Viewer and Editor", link: "../Samples/II_View-Edit-Documents/Built-in-Image-Viewer-and-Editor.html", className: Enum_Demos.imageeditor, screenshotLink: ""
                            },
                            {
                                name: 'Custom image viewer and editor',
                                API: [
                                    {
                                        name: "CurrentImageIndexInBuffer", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/WebTwain_Buffer.html?ver=latest#currentimageindexinbuffer"
                                    },
                                    {
                                        name: "HowManyImagesInBuffer", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/WebTwain_Buffer.html?ver=latest#howmanyimagesinbuffer"
                                    },
									{
                                        name: "Crop()", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/WebTwain_Edit.html#crop"
                                    },
									{
                                        name: "RotateLeft()", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/WebTwain_Edit.html#rotateleft"
                                    },
									{
                                        name: "RemoveAllSelectedImages()", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/WebTwain_Buffer.html#removeallselectedimages"
                                    },
									{
                                        name: "RemoveAllImages()", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/WebTwain_Buffer.html#removeallimages"
                                    },
									{
                                        name: "setViewMode()", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/WebTwain_Viewer.html?ver=latest#setviewmode"
                                    },
									{
                                        name: "previous()", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/WebTwain_Viewer.html#previous"
                                    },
									{
                                        name: "next()", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/WebTwain_Viewer.html#next"
                                    },
									{
                                        name: "first()", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/WebTwain_Viewer.html#first"
                                    },
									{
                                        name: "last()", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/WebTwain_Viewer.html#last"
                                    },
									{
                                        name: "fitWindow()", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/WebTwain_Viewer.html#fitwindow"
                                    },
									{
                                        name: "zoom ", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/WebTwain_Viewer.html#zoom"
                                    }],
                                desc: "Viewer and Editor", link: "../Samples/II_View-Edit-Documents/Custom-Image-Viewer-and-Editor.html", className: Enum_Demos.navigation, screenshotLink: ""
                            },
                            {
                                name: 'Viewer and Thumbnail Navigator',
                                API: [
									{
                                        name: "createThumbnailViewer()", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/WebTwain_Viewer.html#createthumbnailviewer"
                                    },
                                    {
                                        name: "SelectSourceAsync()", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/WebTwain_Acquire.html?ver=latest#selectsourceasync"
                                    },
                                    {
                                        name: "AcquireImageAsync()", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/WebTwain_Acquire.html?ver=latest#acquireimageasync"
                                    }],
                                desc: "Viewer And Thumbnail Navigator", link: "../Samples/II_View-Edit-Documents/Viewer-and-Thumbnail-Navigator.html", className: Enum_Demos.thumbnails, screenshotLink: ""
                            }
                        ]
                },
                {
                    name: "Save/Upload", type: "core", demos:
                        [
							{
                                name: 'Save to HTTP Server',
                                API: [
                                  {
                                      name: "HTTPUpload()", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/WebTwain_IO.html?ver=latest#httpupload"
                                  }],
								desc: "HTTP Upload", link: "../Samples/III_Save-Upload-Documents/Save-Documents-to-HTTP-Server/Introduction.html", className: Enum_Demos.httpupload, screenshotLink:""
                            },
                            {
                                name: 'Save to Local Drive',
                                API: [
                                    {
                                        name: "SaveAsJPEG()", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/WebTwain_IO.html?ver=latest#saveasjpeg"
                                    },
                                    {
                                        name: "SaveAllAsMultiPageTIFF()", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/WebTwain_IO.html?ver=latest#saveallasmultipagetiff"
                                    },
                                    {
                                        name: "SaveAllAsPDF()", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/WebTwain_IO.html?ver=latest#saveallaspdf"
                                    }],
                                desc: "Save to Local Drive", link: "../Samples/III_Save-Upload-Documents/Save-Documents-to-Local-Drive/Save-to-Local-Drive.html", className: Enum_Demos.saveimage, screenshotLink: ""
                            },
                        ]
                },
                {
                    name: "Load/Download", type: "core", demos:
                        [
							{
                                name: 'Download from HTTP Server',
                                API: [
									{
										name: "HTTPDownload()", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/WebTwain_IO.html?ver=latest#httpdownload"
									}
								],
								desc: "Download from HTTP Server", link: "../Samples/IV_Load-Download-Documents/Download-from-HTTP-Server/Visual-Studio-Demo/Download-from-HTTP-Server.html", className: Enum_Demos.httpdownload, screenshotLink: ""
							}, 
                            {
                                name: 'Load from Local Drive',
                                API: [
                                    {
                                        name: "LoadImageEx()", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/WebTwain_IO.html#loadimageex"
                                    }],
                                desc: "Load from Local Drive", link: "../Samples/IV_Load-Download-Documents/Load-from-Local-Drive/Load-from-Local-Drive.html", className: Enum_Demos.loadlocal, screenshotLink: ""
                            }, 
                        ]
                },  
                {
                    name: "PDF Rasterizer", type: "addon", demos:
                        [
                            {
                                name: 'PDF Rasterizer',
                                bExternalLink: false,
                                API: [
                                    {
                                        name: "Addon.PDF.GetReaderOptions()", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/Addon_PDF.html?ver=latest#getreaderoptions"
                                    },
                                    {
                                        name: "Addon.PDF.SetReaderOptions()", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/Addon_PDF.html?ver=latest#setreaderoptions"
                                    },
                                    {
                                        name: "LoadImageEx()", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/WebTwain_IO.html?ver=latest#loadimageex"
                                    }],
                                desc: "PDF Rasterizer", link: "../Samples/V_Optional-Add-ons/PDF-Rasterizer/PDF-Rasterizer.html", className: Enum_Demos.rasterizer, screenshotLink: ""
                            }
                        ]
                },				
				{
                    name: "Barcode Reader", type: "addon", demos:
                        [
                            {
                                name: 'Barcode Reader',
                                //bExternalLink: true,
                                 API: [
                                    {
                                        name: "Addon.BarcodeReader.getRuntimeSettings()", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/Addon_BarcodeReader.html#getruntimesettings"
                                    },
                                    {
                                        name: "Addon.BarcodeReader.updateRuntimeSettings()", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/Addon_BarcodeReader.html#updateruntimesettings"
                                    },
                                    {
                                        name: "Addon.BarcodeReader.decode()", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/Addon_BarcodeReader.html#decode"
                                    }],
                                desc: "Barcode Reader",
                                link: "../Samples/V_Optional-Add-ons/Barcode-Reader/Read-Barcode.html",
                                className: Enum_Demos.scanbarcode,
                                screenshotLink: ""
                            }
                        ]
                },
				{
                    name: "Desktop Webcam", type: "addon", demos:
                        [
                            {
                                name: 'Desktop Webcam',
                                //bExternalLink: true,
                                 API: [
                                    {
                                        name: "Addon.Webcam.CaptureImage()", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/Addon_Webcam.html#captureimage"
                                    },
                                    {
                                        name: "Addon.Webcam.GetSourceList()", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/Addon_Webcam.html#getsourcelist"
                                    },
                                    {
                                        name: "Addon.Webcam.SelectSource()", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/Addon_Webcam.html#selectsource"
                                    },
									{
                                        name: "Addon.Webcam.PlayVideo()", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/Addon_Webcam.html#playvideo"
                                    },
                                    {
                                        name: "Addon.Webcam.StopVideo()", APILink: "https://www.dynamsoft.com/web-twain/docs/info/api/Addon_Webcam.html#stopvideo"
                                    }],
                                desc: "Desktop Webcam",
                                link: "../Samples/V_Optional-Add-ons/Desktop-Webcam/Desktop-Webcam-Capture.html",
                                className: Enum_Demos.scanwebcam,
                                screenshotLink: ""
                            }
                        ]
                }					
            ]
    };

function loadDemos() {
    $("#goback").live("click", function () {
        $(".demo a")[0].click();
    });
    $("#demoCat").empty();
    $("#demoAddonCat").empty();
	Dynamsoft.Lib.asyncGetNavInfo().then(function(_navInfo){
		for (var i = 0; i < aryDemo.categories.length; i++) {
			if (aryDemo.categories[i].demos != null) {
				if (aryDemo.categories[i].type == "addon") {
						for (var j = 0; j < aryDemo.categories[i].demos.length; j++) {
							var o = aryDemo.categories[i].demos[j];	
							if(o.className == Enum_Demos.serversideocr){
								$("#demoAddonCat").append("<li class='demo'><a class='" + o.className + "'>" + o.name + "</a></li>");
							} else if((_navInfo.bEdge && parseInt(_navInfo.strBrowserVersion) >= 80) || ( _navInfo.bEdge && (o.className == Enum_Demos.clientsideocr))){
								 $("#demoAddonCat").append("<li class='demo'><a href='" + o.link + "' target='_blank'>" + o.name + "</a></li>");
							} else {			
								if (o.bExternalLink) {
									$("#demoAddonCat").append("<li class='demo'><a href='" + o.link + "' target='_blank'>" + o.name + "</a></li>");
								}
								else {
									$("#demoAddonCat").append("<li class='demo'><a class='" + o.className + "'>" + o.name + "</a></li>");
								}
							}
						}
				}
				else {
					var strList = "";
					for (var g = 0; g < aryDemo.categories[i].demos.length; g++) {
						var tempClassName = aryDemo.categories[i].demos[g].className;
						if(_navInfo.bEdge && parseInt(_navInfo.strBrowserVersion) >= 80 && tempClassName != Enum_Demos.sendextrainfo)
							strList += "<li class='demo'><a href='" + aryDemo.categories[i].demos[g].link + "' target='_blank'>" + aryDemo.categories[i].demos[g].name + "</a></li>";
						else	
							strList += "<li class='demo'><a class='" + aryDemo.categories[i].demos[g].className + "'>" + aryDemo.categories[i].demos[g].name + "</a></li>";
					}	
					if (i == 0) {
						$("#demoCat").append("<li class='liCat expand'><span>" + aryDemo.categories[i].name + "<i class='fa fa-angle-up'></i></span><ul class='demoList'>" + strList + "</ul></li>");
					}
					else {
						$("#demoCat").append("<li class='liCat'><span>" + aryDemo.categories[i].name + "<i class='fa fa-angle-down'></i></span><ul class='demoList'>" + strList + "</ul></li>");
					}
				}
			}
		}
	});
}

// collapse demos
$("#demoCat li.liCat span").live("click", function () {
    var o = $(this);
    o.parent(".liCat").toggleClass("expand");
    o = o.children();
    if (o.hasClass('fa-angle-up')) {
        o.removeClass('fa-angle-up');
        o.addClass('fa-angle-down');
    } else {
        o.removeClass('fa-angle-down');
        o.addClass('fa-angle-up');
    }
});


$(".demo a").live("click", function () {
	if(this.innerHTML.indexOf("PDF Compressor") == 0)
		return;
    var currentDemo = $(this).attr("class");
    $(".catList li").removeClass("CurrentDemo");
    $(this).closest("li").addClass("CurrentDemo");
    $(".demoCode").hide();
    var strPath = window.location.href;
    strPath = strPath.substring(0, strPath.lastIndexOf("/") + 1);
    var _href = '';
    for (var i = 0; i < aryDemo.categories.length; i++) {
        for (var j = 0; j < aryDemo.categories[i].demos.length; j++) {
            if (aryDemo.categories[i].demos[j].className == currentDemo) {
                $("#demoDesc").html(aryDemo.categories[i].demos[j].desc);
                if (currentDemo == Enum_Demos.mrc){ //(currentDemo == Enum_Demos.scanbarcode || currentDemo == Enum_Demos.scanwebcam) {
                    var _width = '1039px', demoMargin = '0px', _height = '930px';
                    if (currentDemo == Enum_Demos.clientsideocr)
                        _height = '920px';
                    if (currentDemo == Enum_Demos.scanwebcam) {
                        _width = '1121px';
                        demoMargin = '0 0 0 -40px';
                    }
                    $("#goback").show();
                    $("#demoDesc").parent().css('display', 'none');
                    $('#sidebar').css('display', 'none');
                    $('#sampleContent').css({
                        'width': '1039px',
                        'margin-left': '0px',
                        'overflow': 'hidden'
                    });
                    $('.demo-main').css({
                        'width': _width,
                        'margin': demoMargin,
                        'border': '0px',
                        'padding': '0px',
                        'overflow': 'hidden'
                    });
                    $("#frmDemo").css({
                        "margin-top": '-5px',
                        "width": $("#frmDemo").parent().css("width"),
                        "height": _height
                    });
                    $("#Samples").css({
                        'width': '1039px',
                        'margin': '0'
                    });
                    $(".description").css({
                        'margin-left': '50px'
                    });
                } else {
                    $("#goback").hide();
                    $("#demoDesc").parent().css('display', '');
                    $('#sidebar').css('display', 'block');
                    $('#sampleContent').css({
                        'width': '655px',  
                        'margin-left': '17px'  
                    });
                    $('.demo-main').css({
                        'width': '660px',  
                        'margin': '20px 0',
                        'border': '1px solid #ddd',
                        'padding': '5px'
                    });
					if(currentDemo == Enum_Demos.customscan || currentDemo == Enum_Demos.mrc){
						 $("#frmDemo").css({
                        "width": parseInt($("#frmDemo").parent().css("width")) - 10 + "px",
                        "height": '750px'  
                    });
					} else if(currentDemo == Enum_Demos.removeblankpage){
						 $("#frmDemo").css({
                        "width": parseInt($("#frmDemo").parent().css("width")) - 10 + "px",
                        "height": '600px'  
                    });
					} else if(currentDemo == Enum_Demos.scanwebcam || currentDemo == Enum_Demos.rasterizer){
						 $("#frmDemo").css({
                        "width": parseInt($("#frmDemo").parent().css("width")) - 10 + "px",
                        "height": '640px'  
                    });
					} else if(currentDemo == Enum_Demos.httpdownload){
						 $("#frmDemo").css({
                        "width": parseInt($("#frmDemo").parent().css("width")) - 10 + "px",
                        "height": '600px' 
                    });
					} else if(currentDemo == Enum_Demos.scanbarcode){
						 $("#frmDemo").css({
                        "width": parseInt($("#frmDemo").parent().css("width")) - 10 + "px",
                        "height": '800px' 
                    });
					} else if(currentDemo == Enum_Demos.httpupload){
						 $("#frmDemo").css({
                        "width": parseInt($("#frmDemo").parent().css("width")) - 10 + "px",
                        "height": '600px' 
                    });
					} else if(currentDemo == Enum_Demos.navigation || currentDemo == Enum_Demos.mobilewebcapture){
						 $("#frmDemo").css({
                        "width": parseInt($("#frmDemo").parent().css("width")) - 10 + "px",
                        "height": '660px'  
                    });
					} else {
						$("#frmDemo").css({
							"width": parseInt($("#frmDemo").parent().css("width")) - 10 + "px",
							"height": '580px' 
						});
					}
                    $("#Samples").css({
                        'width': '940px',
                        'margin': '0 0 0 35px'
                    });
                    $(".description").css({
                        'margin-left': '0px'
                    });
                }
                if (currentDemo == Enum_Demos.serversideocr || currentDemo == Enum_Demos.mobilecamera || currentDemo == Enum_Demos.mrc) {
                    $('.description').hide();
                } else {
                    $('.description').show();
                }
                /******************If non-IE on Win, view source******************/
                ua = (navigator.userAgent.toLowerCase());
                if (ua.indexOf("msie") == -1 && ua.indexOf('trident') == -1)
                    _href = /*"view-source:" + */strPath;
                /*****************************************************************/
                if (aryDemo.categories[i].demos[j].link != "")
					$("#demoLink").html("The complete source code can be found at <a style='text-decoration: underline; font-weight: bold' href='" + _href + aryDemo.categories[i].demos[j].link + "' target='_blank'>" + strPath + aryDemo.categories[i].demos[j].link + "</a>");
                else
                    $("#demoLink").html("");
                if (aryDemo.categories[i].demos[j].screenshotLink == "") {
                    $("#frmDemo").attr("src", aryDemo.categories[i].demos[j].link);
                }
                else {
                    $("#frmDemo").attr("src", aryDemo.categories[i].demos[j].screenshotLink);
                }
                var strAPI = "";
                if (aryDemo.categories[i].demos[j].API != "") {
                    for (var k = 0; k < aryDemo.categories[i].demos[j].API.length; k++) {
                        if (strAPI != "") {
                            strAPI += ", ";
                        }
                        if (aryDemo.categories[i].demos[j].API[k].APILink != null) {
                            strAPI += "<a href='" + aryDemo.categories[i].demos[j].API[k].APILink + "' target='_blank'>" + aryDemo.categories[i].demos[j].API[k].name + "</a>";
                        }
                        else {
                            strAPI += aryDemo.categories[i].demos[j].API[k].name;
                        }
                    }
                    strAPI = "Main API(s) used in this sample: " + strAPI;
                }
                $("#spnDemoAPIName").html(strAPI);

            }
        }
    }

    $("." + currentDemo + "").show();
});

$("#viewSource").live("click", function () {
    $("#demoSource").toggle();

    var o = $(this).children();
    if (o.hasClass('fa-angle-up')) {
        o.removeClass('fa-angle-up');
        o.addClass('fa-angle-down');
    } else {
        o.removeClass('fa-angle-down');
        o.addClass('fa-angle-up');
    }
});
