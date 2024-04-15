builder.OpenFile("${fileUrl}");
const ext = "${ext}"
var oDocument;
switch (ext) {
    case "doc":
    case "docx":
        oDocument = Api.GetDocument();
        break;
    case "xls":
    case "xlsx":
        oDocument = Api.GetActiveSheet();
        break;
}

var aComments = oDocument.GetAllComments();
for (var i = 0; i < aComments.length; i++) {
    aComments[i].Delete();
}

builder.SaveFile(ext, "output.${ext}"); // Save the document as "output.docx"
builder.CloseFile();
