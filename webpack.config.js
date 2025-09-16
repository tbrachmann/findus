const path = require('path');
const BundleTracker = require('webpack-bundle-tracker');

module.exports = (env, argv) => {
  const isDevelopment = argv.mode === 'development';

  return {
    entry: {
      main: './frontend/src/index.js',
    },
    output: {
      path: path.resolve(__dirname, 'chat/static/chat/js'),
      filename: isDevelopment ? '[name].js' : '[name].[contenthash].js',
      clean: true,
      publicPath: '/static/chat/js/',
    },
    resolve: {
      extensions: ['.js'],
    },
    optimization: {
      splitChunks: {
        chunks: 'all',
        cacheGroups: {
          vendor: {
            test: /[\\/]node_modules[\\/]/,
            name: 'vendors',
            priority: 10,
            reuseExistingChunk: true,
          },
        },
      },
    },
    plugins: [
      new BundleTracker({
        path: __dirname,
        filename: 'webpack-stats.json',
      }),
    ],
    devtool: isDevelopment ? 'eval-source-map' : false,
  };
};
