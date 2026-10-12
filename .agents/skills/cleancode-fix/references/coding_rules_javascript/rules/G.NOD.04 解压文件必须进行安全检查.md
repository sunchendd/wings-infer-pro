# G.NOD.04 解压文件必须进行安全检查

- **规则ID**：49cd97c1-7508-4107-8125-0d826b1886e8
- **更新时间**：2025-06-05 04:25:00

---

**【问题级别】**

一般

**【描述】**

攻击者有可能上传一个很小的zip文件，但是完全解压缩之后达到几百万GB甚至更多，消耗完磁盘空间导致系统或程序无法正常运行。

**【正确示例】**

```
const fs = require('fs');
const pathmodule = require('path');
const JSZip = require('jszip');
const MAX_FILES = 10000;
const MAX_SIZE = 1000000000; // 1 GB
let fileCount = 0;
let totalSize = 0;
let targetDirectory = __dirname + '/archive_tmp';
fs.readFile("foo.zip", function(err, data) {
  if (err) throw err;
  JSZip.loadAsync(data).then(function (zip) {
    zip.forEach(function (relativePath, zipEntry) {
      fileCount++;
      if (fileCount > MAX_FILES) {
        throw 'Reached max. number of files';
      }
      // Prevent ZipSlip path traversal (S6096)
      const resolvedPath = pathmodule.join(targetDirectory, zipEntry.name);
      if (!resolvedPath.startsWith(targetDirectory)) {
        throw 'Path traversal detected';
      }
      if (!zip.file(zipEntry.name)) {
        fs.mkdirSync(resolvedPath);
      } else {
        zip.file(zipEntry.name).async('nodebuffer').then(function (content) {
          totalSize += content.length;
          if (totalSize > MAX_SIZE) {
            throw 'Reached max. size';
          }
          fs.writeFileSync(resolvedPath, content);
        });
      }
    });
  });
});

```
**【错误示例】**

```
解压前未进行以下基础安全检查：
1.文件个数是否超出业务预期个数；
2.文件大小是否超出业务预期大小。

```
**【修复建议】**

在解压前最少进行以下几点基础安全检查：

1.文件个数是否超出业务预期个数；

2.文件大小是否超出业务预期大小。



建议根据需要，依赖其它工程手段加强防范，这些工程手段包括并不限于：

1.为解压文件单独分区，限定大小；

2.对压缩包做健康检查，包括其中内容是否符合业务预期。



以上两点建议非强制执行，正例中展示的是常用的校验方法，不能规避所有问题。

具体问题还需要结合产品特点具体分析，最终使解压后的文件大小在可控范围内。
