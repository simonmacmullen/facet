<html prefix="og: http://ogp.me/ns#">
  <head>
    <title>Image <?php echo $_GET['id']; ?></title>
    <meta property="og:title" content="Image <?php echo $_GET['id']; ?>" />
    <meta property="og:description" content="<?php echo $_GET['keywords']; ?>" />
    <meta property="og:image" content="<?php echo $_GET['image']; ?>" />
    <meta http-equiv="refresh" content="0;URL='<?php echo $_GET['redirect']; ?>'" />
  </head>
</html>
