var DWTObject, blankField = "",
    extrFieldsCount = 0, upload_returnSth = true,
    strHTTPServer = location.hostname, strActionPage, strFullActionPagePath, ObjString,
    CurrentPathName = unescape(location.pathname),
    CurrentPath = CurrentPathName.substring(0, CurrentPathName.lastIndexOf("/") + 1);

function addAField() {
    extrFieldsCount++;
    if (extrFieldsCount == 3) {
        document.getElementById('div-extra-fields').style.overflowY = 'scroll';
    }
    if (document.getElementById('div-extra-fields').style.display == "none")
        document.getElementById('div-extra-fields').style.display = '';
    else {
        document.getElementById('div-extra-fields').appendChild(blankField);
        blankField = document.getElementsByClassName('div-fields-item')[extrFieldsCount - 1].cloneNode(true);

        var element = document.getElementById("div-extra-fields");
        element.scrollTop = element.scrollHeight;
    }

}

Dynamsoft.DWT.RegisterEvent("OnWebTwainReady", function () {
    blankField = document.getElementsByClassName('div-fields-item')[0].cloneNode(true);
    DWTObject = Dynamsoft.DWT.GetWebTwain('dwtcontrolContainer');
    if (DWTObject) {
        DWTObject.Viewer.width = 505;
        DWTObject.Viewer.height = 600;
    }
});

function AcquireImage() {
    if (DWTObject) {
        DWTObject.SelectSourceAsync().then(function () {
            return DWTObject.AcquireImageAsync({
                IfDisableSourceAfterAcquire: true // Scanner source will be disabled/closed automatically after the scan.
            });
        }).catch(function (exp) {
            alert(exp.message);
        });
    }
}

var bUpload = false;
function LoadImages() {
    if (DWTObject) {
        bUpload = false;
        DWTObject.IfShowFileDialog = true;
        DWTObject.LoadImageEx('', 5,
            function () {
            },
            function (errorCode, errorString) {
                alert('Load Image:' + errorString);
            }
        );
    }
}

function OnHttpUploadSuccess() {
    console.log('successful');
}

function OnHttpServerReturnedSomething(errorCode, errorString, sHttpResponse) {
    if (errorCode != 0 && errorCode != -2003)
        alert(errorString);
    else {
        var textFromServer = sHttpResponse;
        _printUploadedFiles(textFromServer);
    }
}

function _printUploadedFiles(info) {
    //console.log(info);
    if (info.indexOf('DWTUploadFileName') != -1) {
        var url, _strPort;
        DWTObject.IfSSL = Dynamsoft.Lib.detect.ssl;
        _strPort = location.port == "" ? 80 : location.port;
        url = 'http://' + location.hostname + ':' + location.port;
        if (Dynamsoft.Lib.detect.ssl == true) {
            _strPort = location.port == "" ? 443 : location.port;
            url = 'https://' + location.hostname + ':' + location.port;
        }
        var fileName = info.substring(info.indexOf('DWTUploadFileName') + 18, info.indexOf('UploadedFileSize'));
        var fileSize = info.substr(info.indexOf('UploadedFileSize') + 17);
        url += CurrentPath + 'UploadedImages/' + encodeURI(fileName);
        var newTR = document.createElement('tr');
        _str = "<td class='tc'><a class='bluelink'" + ' href="' + url + '" target="_blank">' + fileName + "</a></td>" + "<td class='tc'>" + fileSize + '</td>';
        if (info.indexOf("FieldsTrue:") != -1)
            _str += "<td class='tc'><a class='bluelink'" + '" href="' + url.substring(0, url.length - 4) + '_1.txt' + '" target="_blank">Fields</td>';
        else {
            _str += "<td class='tc'>No Fields</td>";
        }
        newTR.innerHTML = _str;
        document.getElementById('div-uploadedFile').appendChild(newTR);

        var element = document.getElementById("resultWrap");
        element.scrollTop = element.scrollHeight;
    }
}

function upload_preparation(_name) {
    DWTObject.IfShowProgressBar = !document.getElementById('quietScan').checked;
    strActionPage = CurrentPath + 'SaveToFile.aspx';
    DWTObject.IfSSL = Dynamsoft.Lib.detect.ssl;
    var _strPort = location.port == "" ? 80 : location.port;
    if (Dynamsoft.Lib.detect.ssl == true) {
        _strPort = location.port == "" ? 443 : location.port;
        strFullActionPagePath = "https://" + strHTTPServer + ":" + _strPort + strActionPage;
    } else {
        strFullActionPagePath = "http://" + strHTTPServer + ":" + _strPort + strActionPage;
    }

    DWTObject.HTTPPort = _strPort;
    /* Add Fields to the Post */
    var fields = document.getElementsByClassName('div-fields-item');

    DWTObject.ClearAllHTTPFormField();
    for (var n = 0; n < fields.length; n++) {
        var o = fields[n];
        if (o.children[0].value != '')
            DWTObject.SetHTTPFormField(o.children[0].value, o.children[1].value);
    }
}

function UploadImage_inner() {
    if (DWTObject.HowManyImagesInBuffer == 0)
        return;

    var i, aryIndices = [], Digital = new Date(),
        uploadfilename = Digital.getMilliseconds();
    upload_preparation(uploadfilename);

    var imageType = Dynamsoft.DWT.EnumDWT_ImageType.IT_JPG;
    var extension = ".jpg";
    if (document.getElementsByName('ImageType')[1].checked) {
        imageType = Dynamsoft.DWT.EnumDWT_ImageType.IT_TIF;
        extension = ".tif";
    } else if (document.getElementsByName('ImageType')[2].checked) {
        imageType = Dynamsoft.DWT.EnumDWT_ImageType.IT_PDF;
        extension = ".pdf";
    } else if (document.getElementsByName('ImageType')[3].checked) {
        imageType = Dynamsoft.DWT.EnumDWT_ImageType.IT_PNG;
        extension = ".png";
    }

    aryIndices = [];
    var count = DWTObject.HowManyImagesInBuffer;
    for (i = 0; i < count; i++) aryIndices.push(i);

    if (document.getElementsByName('ImageType')[0].checked || document.getElementsByName('ImageType')[3].checked) {
        var uploadJPGsOneByOne = function (errorCode, errorString, sHttpResponse) {
            if (errorCode != 0 && errorCode != -2003) {
                alert(errorString);
                return;
            }

            if (upload_returnSth)
                _printUploadedFiles(sHttpResponse);
            if (aryIndices.length > 0) {
                if (upload_returnSth)
                    DWTObject.HTTPUpload(strFullActionPagePath, aryIndices.splice(0, 1), imageType, Dynamsoft.DWT.EnumDWT_UploadDataFormat.Binary, uploadfilename + "-" + (count - aryIndices.length) + extension, OnHttpUploadSuccess, uploadJPGsOneByOne);
                else
                    DWTObject.HTTPUpload(strFullActionPagePath, aryIndices.splice(0, 1), imageType, Dynamsoft.DWT.EnumDWT_UploadDataFormat.Binary, uploadfilename + "-" + (count - aryIndices.length) + extension, uploadJPGsOneByOne, OnHttpServerReturnedSomething);
            }
        };
        if (upload_returnSth)
            DWTObject.HTTPUpload(strFullActionPagePath, aryIndices.splice(0, 1), imageType, Dynamsoft.DWT.EnumDWT_UploadDataFormat.Binary, uploadfilename + "-" + (count - aryIndices.length) + extension, OnHttpUploadSuccess, uploadJPGsOneByOne);
        else
            DWTObject.HTTPUpload(strFullActionPagePath, aryIndices.splice(0, 1), imageType, Dynamsoft.DWT.EnumDWT_UploadDataFormat.Binary, uploadfilename + "-" + (count - aryIndices.length) + extension, uploadJPGsOneByOne, OnHttpServerReturnedSomething);

    } else if (document.getElementsByName('ImageType')[1].checked || document.getElementsByName('ImageType')[2].checked) {
        DWTObject.HTTPUpload(strFullActionPagePath, aryIndices, imageType, Dynamsoft.DWT.EnumDWT_UploadDataFormat.Binary, uploadfilename + extension, OnHttpUploadSuccess, OnHttpServerReturnedSomething);
    }
}


function UploadImage() {
    if (DWTObject) {
        var nCount = 0, nCountUpLoaded = 0;
        aryFilePaths = [];
        UploadImage_inner();
    }
}
