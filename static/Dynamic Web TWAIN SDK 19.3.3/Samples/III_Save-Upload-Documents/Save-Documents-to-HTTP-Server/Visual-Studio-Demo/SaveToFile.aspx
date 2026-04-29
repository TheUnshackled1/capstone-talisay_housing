<%@ Page Language="C#" %>
<%
    try
    {
        string strImageName, strImageSize;
        HttpFileCollection files = HttpContext.Current.Request.Files;
        HttpPostedFile uploadfile = files["RemoteFile"];
        strImageName = uploadfile.FileName;
        strImageSize = Convert.ToString(Convert.ToInt32(uploadfile.ContentLength / 1024)) + "KB";
        string strImageSavePath = Server.MapPath(".") + "\\UploadedImages\\";
        if (!System.IO.Directory.Exists(strImageSavePath))
        {
            System.IO.Directory.CreateDirectory(strImageSavePath);
        }
        String strInputFile = strImageSavePath + strImageName;

        uploadfile.SaveAs(strInputFile);
        string path = strInputFile.Substring(0, strInputFile.Length - 4) + "_1.txt";
        int fieldsCount = HttpContext.Current.Request.Form.Count;
        string _fields = "";
        if(fieldsCount > 0){
            _fields = "FieldsTrue:";
            if (!System.IO.File.Exists(path))
            {
                using (System.IO.FileStream fs = new System.IO.FileStream(path, System.IO.FileMode.Create, System.IO.FileAccess.Write))
                {
                    using (System.IO.StreamWriter sw = new System.IO.StreamWriter(fs, Encoding.UTF8))
                    {
                        for (int i = 0; i < fieldsCount; i++)
                        {
                            // Create a file to write to.
                            sw.WriteLine(HttpContext.Current.Request.Form.Keys[i] + " :  " + HttpContext.Current.Request.Form[HttpContext.Current.Request.Form.Keys[i]] + Environment.NewLine);
                        }
                    }
                }
            }
        }
        Response.Write(_fields + "DWTUploadFileName:" + strImageName + "UploadedFileSize:" + strImageSize);
    }
    catch
    {
    }
%>